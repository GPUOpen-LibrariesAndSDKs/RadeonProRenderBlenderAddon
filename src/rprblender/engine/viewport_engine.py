import threading
import time
import math
from dataclasses import dataclass

import bpy
import bgl
from gpu_extras.presets import draw_texture_2d
from bpy_extras import view3d_utils

import pyrpr
from .engine import Engine
from rprblender.export import camera, material, world, object, instance, particle
from rprblender.utils import gl
from rprblender import utils
from rprblender import config

from rprblender.utils import logging
log = logging.Log(tag='ViewportEngine')


@dataclass(init=False, eq=True)
class ViewportSettings:
    """
    Comparable dataclass which holds render settings for ViewportEngine:
    - camera viewport settings
    - render resolution
    - screen resolution
    - render border
    """

    camera_data: camera.CameraData
    width: int
    height: int
    screen_width: int
    screen_height: int
    border: tuple

    def __init__(self, context: bpy.types.Context):
        """Initializes settings from Blender's context"""
        self.camera_data = camera.CameraData.init_from_context(context)
        self.screen_width, self.screen_height = context.region.width, context.region.height

        scene = context.scene

        # getting render border
        x1, y1 = 0, 0
        x2, y2 = self.screen_width, self.screen_height
        if context.region_data.view_perspective == 'CAMERA':
            if scene.render.use_border:
                # getting border corners from camera view

                # getting screen camera points
                camera_obj = scene.camera
                camera_points = camera_obj.data.view_frame(scene=scene)
                screen_points = tuple(
                    view3d_utils.location_3d_to_region_2d(context.region,
                                                          context.space_data.region_3d,
                                                          camera_obj.matrix_world @ p)
                    for p in camera_points
                )

                # getting camera view region
                x1 = min(p[0] for p in screen_points)
                x2 = max(p[0] for p in screen_points)
                y1 = min(p[1] for p in screen_points)
                y2 = max(p[1] for p in screen_points)

                # adjusting region to border
                x, y = x1, y1
                dx, dy = x2 - x1, y2 - y1
                x1 = int(x + scene.render.border_min_x * dx)
                x2 = int(x + scene.render.border_max_x * dx)
                y1 = int(y + scene.render.border_min_y * dy)
                y2 = int(y + scene.render.border_max_y * dy)

                # adjusting to region screen resolution
                x1 = max(min(x1, self.screen_width), 0)
                x2 = max(min(x2, self.screen_width), 0)
                y1 = max(min(y1, self.screen_height), 0)
                y2 = max(min(y2, self.screen_height), 0)

        else:
            if context.space_data.use_render_border:
                # getting border corners from viewport camera

                x, y = x1, y1
                dx, dy = x2 - x1, y2 - y1
                x1 = int(x + context.space_data.render_border_min_x * dx)
                x2 = int(x + context.space_data.render_border_max_x * dx)
                y1 = int(y + context.space_data.render_border_min_y * dy)
                y2 = int(y + context.space_data.render_border_max_y * dy)

        # getting render resolution and render border
        self.width, self.height = x2 - x1, y2 - y1
        self.border = (x1, y1), (self.width, self.height)

        if scene.rpr.viewport_limits.limit_viewport_resolution and self.width * self.height > 0:
            # changing render resolution in case of enabled limit_viewport_resolution property

            render_w = int(scene.render.resolution_x * scene.render.resolution_percentage / 100.0)
            render_h = int(scene.render.resolution_y * scene.render.resolution_percentage / 100.0)

            region_aspect = self.width / self.height
            render_aspect = render_w / render_h

            if render_aspect > region_aspect:
                # if render resolution is wider, use the max height
                # from render and scale to aspect ratio
                self.height = min(render_h, self.height)
                self.width = int(region_aspect * self.height)
            else:
                # scale to render width and maintain aspect ratio
                self.width = min(render_w, self.width)
                self.height = int(self.width / region_aspect)

    def export_camera(self, rpr_camera):
        """Exports camera settings with render border"""
        self.camera_data.export(rpr_camera,
            ((self.border[0][0] / self.screen_width, self.border[0][1] / self.screen_height),
             (self.border[1][0] / self.screen_width, self.border[1][1] / self.screen_height)))


@dataclass(init=False, eq=True)
class ShadingData:
    type: str
    use_scene_lights: bool = True
    use_scene_world: bool = True
    studio_light: str = None
    studio_light_rotate_z: float = 0.0
    studio_light_background_alpha: float = 0.0

    def __init__(self, context: bpy.types.Context):
        shading = context.area.spaces.active.shading

        self.type = shading.type
        if self.type == 'RENDERED':
            return

        self.use_scene_lights = shading.use_scene_lights
        self.use_scene_world = shading.use_scene_world
        if not self.use_scene_world:
            self.studio_light = shading.selected_studio_light.path
            if not self.studio_light:
                self.studio_light = str(utils.blender_data_dir() /
                                        "studiolights/world" / shading.studio_light)
            self.studio_light_rotate_z = shading.studiolight_rotate_z
            self.studio_light_background_alpha = shading.studiolight_background_alpha


class ViewportEngine(Engine):
    """ Viewport render engine """

    TYPE = 'VIEWPORT'

    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)
        self.is_synced = False
        self.render_iterations = 0
        self.render_time = 0
        self.iteration = 0
        self.time_begin = 0.0
        self.time_render = 0.0

        self.is_last_iteration = False
        self.image_filter_ready = False

        self.gl_texture: gl.GLTexture = None
        self.viewport_settings: ViewportSettings = None
        self.world_settings: world.WorldData = None
        self.shading_data: ShadingData = None

        self.render_thread: threading.Thread = None
        self.restart_render_event = threading.Event()
        self.lock = threading.Lock()
        self.finish_render = False

    def render(self):
        self.finish_render = False
        self.restart_render_event.clear()

        self.render_thread = threading.Thread(target=ViewportEngine._do_render, args=(self,))
        self.render_thread.start()

    def stop_render(self):
        if not self.render_thread:
            return

        self.finish_render = True
        self.restart_render_event.set()
        self.render_thread.join()

    def notify_status(self, info):
        self.rpr_engine.update_stats("", info)

    def _do_render(self):
        """
        Thread function for self.render_thread. It always run during viewport render.
        If it doesn't render it waits for self.restart_render_event
        """

        log("Start render thread")

        is_adaptive = self.rpr_context.is_aov_enabled(pyrpr.AOV_VARIANCE)

        while True:
            self.restart_render_event.wait()

            if self.finish_render:
                break

            self.iteration = 0
            self.time_begin = 0.0
            self.time_render = 0.0
            if is_adaptive:
                all_pixels = active_pixels = self.rpr_context.width * self.rpr_context.height

            self.is_last_iteration = False
            while not self.is_last_iteration:
                if self.finish_render:
                    break

                is_adaptive_active = is_adaptive and \
                                     self.iteration >= self.rpr_context.get_parameter('as.minspp')

                if self.restart_render_event.is_set():
                    self.restart_render_event.clear()
                    self.iteration = 0
                    self.rpr_context.sync_auto_adapt_subdivision()
                    self.rpr_context.sync_portal_lights()
                    self.time_begin = time.perf_counter()
                    log(f"Restart render [{self.rpr_context.width}, {self.rpr_context.height}]")

                log_str = f"Render iteration: {self.iteration} / {self.render_iterations}"
                if is_adaptive_active:
                    log_str += f", active_pixels: {active_pixels}"
                log(log_str)

                with self.lock:
                    self.rpr_context.render(restart=(self.iteration == 0))

                self.iteration += 1
                self.time_render = time.perf_counter() - self.time_begin

                if is_adaptive_active:
                    active_pixels = self.rpr_context.get_info(pyrpr.CONTEXT_ACTIVE_PIXEL_COUNT, int)
                    if active_pixels == 0:
                        self.is_last_iteration = True

                if self.render_iterations > 0:
                    info_str = f"Time: {self.time_render:.1f} sec"\
                               f" | Iteration: {self.iteration}/{self.render_iterations}"
                else:
                    info_str = f"Time: {self.time_render:.1f}/{self.render_time} sec"\
                               f" | Iteration: {self.iteration}"
                if is_adaptive_active:
                    active_pixels = self.rpr_context.get_info(pyrpr.CONTEXT_ACTIVE_PIXEL_COUNT, int)
                    adaptive_progress = max((all_pixels - active_pixels) / all_pixels, 0.0)
                    info_str += f" | Adaptive Sampling: {math.floor(adaptive_progress * 100)}%"

                self.notify_status(info_str)

                if self.render_iterations > 0:
                    if self.iteration >= self.render_iterations:
                        self.is_last_iteration = True
                else:
                    if self.time_render >= self.render_time:
                        self.is_last_iteration = True
                if is_adaptive and active_pixels == 0:
                    self.is_last_iteration = True

                self.rpr_engine.tag_redraw()

        log("Finish render thread")

    def sync(self, context, depsgraph):
        log('Start sync')
    
        scene = depsgraph.scene
        viewport_limits = scene.rpr.viewport_limits
        view_layer = depsgraph.view_layer

        scene.rpr.init_rpr_context(self.rpr_context, is_final_engine=False,
                                   use_gl_interop=config.use_gl_interop)

        self.shading_data = ShadingData(context)

        # getting initial render resolution
        viewport_settings = ViewportSettings(context)
        width, height = viewport_settings.width, viewport_settings.height
        if width * height == 0:
            # if width, height == 0, 0, then we set it to 1, 1 to be able to set AOVs
            width, height = 1, 1

        self.rpr_context.resize(width, height)
        if not self.rpr_context.gl_interop:
            self.gl_texture = gl.GLTexture(width, height)
        
        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)

        if viewport_limits.noise_threshold > 0.0 and scene.rpr.get_devices(False).count() == 1:
            # if adaptive is enable turn on aov and settings
            self.rpr_context.enable_aov(pyrpr.AOV_VARIANCE)
            viewport_limits.set_adaptive_params(self.rpr_context)

        self.world_settings = self._get_world_settings(depsgraph)
        self.world_settings.export(self.rpr_context)

        self.rpr_context.scene.set_name(scene.name)

        rpr_camera = self.rpr_context.create_camera()
        rpr_camera.set_name("Camera")
        self.rpr_context.scene.set_camera(rpr_camera)

        # exporting objects
        for obj in self.depsgraph_objects(depsgraph):
            object.sync(self.rpr_context, obj)

            if len(obj.particle_systems):
                # export particles
                for particle_system in obj.particle_systems:
                    particle.sync(self.rpr_context, particle_system, obj)

        # exporting instances
        for inst in self.depsgraph_instances(depsgraph):
            instance.sync(self.rpr_context, inst)

        # shadow catcher
        self.rpr_context.sync_catchers()

        # image filter
        image_filter_settings = view_layer.rpr.denoiser.get_settings()
        image_filter_settings['resolution'] = (self.rpr_context.width, self.rpr_context.height)
        self.setup_image_filter(image_filter_settings)

        # other context settings
        self.rpr_context.set_parameter('preview', True)
        self.rpr_context.set_parameter('iterations', 1)
        scene.rpr.export_render_mode(self.rpr_context)
        scene.rpr.export_ray_depth(self.rpr_context)

        self.render_iterations, self.render_time = (viewport_limits.max_samples, 0) 

        self.is_synced = True
        log('Finish sync')

    def sync_update(self, context, depsgraph):
        """ sync just the updated things """

        # get supported updates and sort by priorities
        updates = []
        for obj_type in (bpy.types.Scene, bpy.types.World, bpy.types.Material, bpy.types.Object, bpy.types.Collection):
            updates.extend(update for update in depsgraph.updates if isinstance(update.id, obj_type))

        sync_collection = False
        sync_world = False
        is_updated = False

        shading_data = ShadingData(context)
        if self.shading_data != shading_data:
            sync_world = True

            if self.shading_data.use_scene_lights != shading_data.use_scene_lights:
                sync_collection = True

            self.shading_data = shading_data

        with self.lock:
            for update in updates:
                obj = update.id
                log("sync_update", obj)
                if isinstance(obj, bpy.types.Scene):
                    is_updated |= self.update_render(obj, depsgraph.view_layer)

                    # Outliner object visibility change will provide us only bpy.types.Scene update
                    # That's why we need to sync objects collection in the end
                    sync_collection = True

                    continue

                if isinstance(obj, bpy.types.Material):
                    material.sync_update(self.rpr_context, obj)
                    is_updated |= self.update_material_on_scene_objects(obj, depsgraph)
                    continue

                if isinstance(obj, bpy.types.Object):
                    if obj.type == 'CAMERA':
                        continue

                    is_updated |= object.sync_update(self.rpr_context, obj,
                                                     update.is_updated_geometry, update.is_updated_transform)
                    continue

                if isinstance(obj, bpy.types.World):
                    sync_world = True

                if isinstance(obj, bpy.types.Collection):
                    sync_collection = True
                    continue

            if sync_world:
                world_settings = self._get_world_settings(depsgraph)
                if self.world_settings != world_settings:
                    self.world_settings = world_settings
                    self.world_settings.export(self.rpr_context)
                    is_updated = True

            if sync_collection:
                is_updated |= self.sync_objects_collection(depsgraph)

        if is_updated:
            self.restart_render_event.set()

    @staticmethod
    def _draw_texture(texture_id, x, y, width, height):
        # INITIALIZATION

        # Getting shader program
        shader_program = bgl.Buffer(bgl.GL_INT, 1)
        bgl.glGetIntegerv(bgl.GL_CURRENT_PROGRAM, shader_program)

        # Generate vertex array
        vertex_array = bgl.Buffer(bgl.GL_INT, 1)
        bgl.glGenVertexArrays(1, vertex_array)

        texturecoord_location = bgl.glGetAttribLocation(shader_program[0], "texCoord")
        position_location = bgl.glGetAttribLocation(shader_program[0], "pos")

        # Generate geometry buffers for drawing textured quad
        position = [x, y, x + width, y, x + width, y + height, x, y + height]
        position = bgl.Buffer(bgl.GL_FLOAT, len(position), position)
        texcoord = [0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0]
        texcoord = bgl.Buffer(bgl.GL_FLOAT, len(texcoord), texcoord)

        vertex_buffer = bgl.Buffer(bgl.GL_INT, 2)
        bgl.glGenBuffers(2, vertex_buffer)
        bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, vertex_buffer[0])
        bgl.glBufferData(bgl.GL_ARRAY_BUFFER, 32, position, bgl.GL_STATIC_DRAW)
        bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, vertex_buffer[1])
        bgl.glBufferData(bgl.GL_ARRAY_BUFFER, 32, texcoord, bgl.GL_STATIC_DRAW)
        bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, 0)

        # DRAWING
        bgl.glActiveTexture(bgl.GL_TEXTURE0)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, texture_id)

        bgl.glBindVertexArray(vertex_array[0])
        bgl.glEnableVertexAttribArray(texturecoord_location)
        bgl.glEnableVertexAttribArray(position_location)

        bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, vertex_buffer[0])
        bgl.glVertexAttribPointer(position_location, 2, bgl.GL_FLOAT, bgl.GL_FALSE, 0, None)
        bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, vertex_buffer[1])
        bgl.glVertexAttribPointer(texturecoord_location, 2, bgl.GL_FLOAT, bgl.GL_FALSE, 0, None)
        bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, 0)

        bgl.glDrawArrays(bgl.GL_TRIANGLE_FAN, 0, 4)

        bgl.glBindVertexArray(0)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, 0)

        # DELETING
        bgl.glDeleteBuffers(2, vertex_buffer)
        bgl.glDeleteVertexArrays(1, vertex_array)

    def _resize(self, width, height):
        self.rpr_context.resize(width, height)

        if self.gl_texture:
            self.gl_texture = gl.GLTexture(width, height)

        if self.image_filter:
            image_filter_settings = self.image_filter_settings.copy()
            image_filter_settings['resolution'] = (self.rpr_context.width, self.rpr_context.height)
            self.setup_image_filter(image_filter_settings)

    def draw(self, context):
        log("Draw")

        with self.lock:
            viewport_settings = ViewportSettings(context)
            scene = context.scene

            if viewport_settings.width * viewport_settings.height == 0:
                return

            if self.viewport_settings != viewport_settings:
                viewport_settings.export_camera(self.rpr_context.scene.camera)

                if self.rpr_context.width != viewport_settings.width \
                        or self.rpr_context.height != viewport_settings.height:
                    self._resize(viewport_settings.width, viewport_settings.height)

                self.viewport_settings = viewport_settings
                self.restart_render_event.set()

            self.rpr_context.resolve()
            self.image_filter_ready = False

            if self.is_last_iteration:
                self.time_render = time.perf_counter() - self.time_begin

                if self.image_filter:
                    self.notify_status(f"Time: {self.time_render:.1f} sec"
                                       f" | Iteration: {self.iteration} | Denoising...")
                    self.rpr_engine.tag_redraw()

                    self.update_image_filter_inputs()
                    self.image_filter.run()
                    self.image_filter_ready = True

                    self.time_render = time.perf_counter() - self.time_begin
                    self.notify_status(f"Rendering Done | Time: {self.time_render:.1f} sec"
                                       f" | Iteration: {self.iteration} | Denoised")

                else:
                    self.notify_status(f"Rendering Done | Time: {self.time_render:.1f} sec"
                                       f" | Iteration: {self.iteration}")

            if self.image_filter_ready:
                im = self.image_filter.get_data()
                self.gl_texture.set_image(im)
                texture_id = self.gl_texture.texture_id

            else:
                if self.rpr_context.gl_interop:
                    texture_id = self.rpr_context.get_frame_buffer().texture_id
                else:
                    im = self.rpr_context.get_image()

                    self.gl_texture.set_image(im)
                    texture_id = self.gl_texture.texture_id

            if scene.rpr.render_mode in ('WIREFRAME', 'MATERIAL_INDEX',
                                         'POSITION', 'NORMAL', 'TEXCOORD'):
                # Draw without color management
                draw_texture_2d(texture_id, self.viewport_settings.border[0],
                                *self.viewport_settings.border[1])

            else:
                # Bind shader that converts from scene linear to display space,
                bgl.glEnable(bgl.GL_BLEND)
                bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE_MINUS_SRC_ALPHA)
                self.rpr_engine.bind_display_space_shader(scene)

                # note this has to draw to region size, not scaled down size
                self._draw_texture(texture_id, *self.viewport_settings.border[0],
                                   *self.viewport_settings.border[1])

                self.rpr_engine.unbind_display_space_shader()
                bgl.glDisable(bgl.GL_BLEND)

        log("Finish Draw")

    def sync_objects_collection(self, depsgraph):
        """
        Removes objects which are not present in depsgraph anymore.
        Adds objects which are not present in rpr_context but existed in depsgraph
        """

        # set of depsgraph object keys
        depsgraph_keys = set.union(
            set(object.key(obj) for obj in self.depsgraph_objects(depsgraph)),
            set(instance.key(obj) for obj in self.depsgraph_instances(depsgraph))
        )

        # set of visible rpr object keys
        rpr_object_keys = set(key for key, obj in self.rpr_context.objects.items()
                              if not isinstance(obj, pyrpr.Shape) or obj.is_visible)

        # sets of objects keys to remove from rpr
        object_keys_to_remove = rpr_object_keys - depsgraph_keys

        # sets of objects keys to export into rpr
        object_keys_to_export = depsgraph_keys - rpr_object_keys

        res = False
        if object_keys_to_remove:
            log("Object keys to remove", object_keys_to_remove)
            for obj_key in object_keys_to_remove:
                if obj_key in self.rpr_context.objects:
                    self.rpr_context.remove_object(obj_key)
                    res = True

        if object_keys_to_export:
            log("Object keys to add", object_keys_to_export)

            # exporting objects
            for obj in self.depsgraph_objects(depsgraph):
                obj_key = object.key(obj)
                if obj_key not in object_keys_to_export:
                    continue

                rpr_obj = self.rpr_context.objects.get(obj_key, None)
                if rpr_obj:
                    rpr_obj.set_visibility(True)
                else:
                    object.sync(self.rpr_context, obj)

                res = True

            # exporting instances
            for inst in self.depsgraph_instances(depsgraph):
                if instance.key(inst) not in object_keys_to_export:
                    continue

                instance.sync(self.rpr_context, inst)
                res = True

        return res

    def update_material_on_scene_objects(self, mat, depsgraph):
        """ Find all mesh material users and reapply material """
        rpr_material = self.rpr_context.materials.get(material.key(mat), None)
        rpr_displacement = self.rpr_context.materials.get(material.key(mat, 'Displacement'), None)
        if not rpr_material and not rpr_displacement:
            return False

        objects = tuple(obj for obj in self.depsgraph_objects(depsgraph)
                            if mat.name in obj.material_slots.keys())
        updated = False
        for obj in objects:
            if object.key(obj) not in self.rpr_context.objects:
                object.sync(self.rpr_context, obj)
                updated = True
                continue

            updated |= object.sync_update(self.rpr_context, obj, False, False)

        return updated

    def update_render(self, scene: bpy.types.Scene, view_layer: bpy.types.ViewLayer):
        ''' update settings if changed while live returns True if restart needed'''
        restart = scene.rpr.export_render_mode(self.rpr_context)
        restart |= scene.rpr.export_ray_depth(self.rpr_context)

        render_iterations, render_time = (scene.rpr.viewport_limits.max_samples, 0)

        if self.render_iterations != render_iterations or self.render_time != render_time:
            self.render_iterations = render_iterations
            self.render_time = render_time
            restart = True

        restart |= scene.rpr.viewport_limits.set_adaptive_params(self.rpr_context)

        # image filter
        image_filter_settings = view_layer.rpr.denoiser.get_settings()
        image_filter_settings['resolution'] = (self.rpr_context.width, self.rpr_context.height)
        if self.image_filter_settings != image_filter_settings:
            self.setup_image_filter(image_filter_settings)
            restart = True

        return restart

    def _enable_image_filter(self, settings):
        super()._enable_image_filter(settings)
        self.image_filter_ready = False

        if not self.gl_texture:
            self.gl_texture = gl.GLTexture(self.rpr_context.width, self.rpr_context.height)

    def _disable_image_filter(self):
        super()._disable_image_filter()
        self.image_filter_ready = False

    def _get_world_settings(self, depsgraph):
        if self.shading_data.use_scene_world:
            return world.WorldData.init_from_world(depsgraph.scene.world)

        return world.WorldData.init_from_shading_data(self.shading_data)

    def depsgraph_objects(self, depsgraph, with_camera=False):
        for obj in super().depsgraph_objects(depsgraph, with_camera):
            if obj.type == 'LIGHT' and not self.shading_data.use_scene_lights:
                continue

            yield obj
