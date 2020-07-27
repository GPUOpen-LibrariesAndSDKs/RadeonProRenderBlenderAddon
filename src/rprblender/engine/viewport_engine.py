#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
import threading
import time
import math
from dataclasses import dataclass
import traceback
import textwrap

import bpy
import bgl
from gpu_extras.presets import draw_texture_2d
from bpy_extras import view3d_utils

import pyrpr
from .engine import Engine
from rprblender.export import camera, material, world, object, instance, particle
from rprblender.export.mesh import assign_materials
from rprblender.utils import gl
from rprblender import utils
from rprblender.utils.user_settings import get_user_settings

from rprblender.utils import logging
log = logging.Log(tag='viewport_engine')


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

    def export_camera(self, rpr_camera):
        """Exports camera settings with render border"""
        self.camera_data.export(rpr_camera,
            ((self.border[0][0] / self.screen_width, self.border[0][1] / self.screen_height),
             (self.border[1][0] / self.screen_width, self.border[1][1] / self.screen_height)))

    def adapt_resolution(self, requested_ratio, prev_settings, min_scale):
        MIN_PIXEL_DIFF = 0.2
        MIN_RATIO_DIFF = 0.1

        # checking with previous settings, if previous resolution
        # suits to requested_pixels and suits to new render ratio
        if abs(1 - requested_ratio) < MIN_PIXEL_DIFF \
                and abs(self.width / self.height -
                        prev_settings.width / prev_settings.height) < MIN_RATIO_DIFF:
            self.width = max(prev_settings.width, int(self.width * min_scale), 1)
            self.height = max(prev_settings.height, int(self.height * min_scale), 1)
            return

        # checking if current resolution suits to requested_pixels
        new_ratio = (prev_settings.width * prev_settings.height * requested_ratio) / \
                    (self.width * self.height)
        if new_ratio > 1.0 - MIN_PIXEL_DIFF:
            return

        # changing to new resolution, but not less then SCALE_MIN
        scale = max(math.sqrt(new_ratio), min_scale)
        self.width = max(int(self.width * scale), 1)
        self.height = max(int(self.height * scale), 1)


@dataclass(init=False, eq=True)
class ShadingData:
    type: str
    use_scene_lights: bool = True
    use_scene_world: bool = True
    studio_light: str = None
    studio_light_rotate_z: float = 0.0
    studio_light_background_alpha: float = 0.0
    studio_light_intensity: float = 1.0

    def __init__(self, context: bpy.types.Context):
        shading = context.area.spaces.active.shading

        self.type = shading.type
        if self.type == 'RENDERED':
            self.use_scene_lights = shading.use_scene_lights_render
            self.use_scene_world = shading.use_scene_world_render
        else:
            self.use_scene_lights = shading.use_scene_lights
            self.use_scene_world = shading.use_scene_world

        if not self.use_scene_world:
            self.studio_light = shading.selected_studio_light.path
            if not self.studio_light:
                self.studio_light = str(utils.blender_data_dir() /
                                        "studiolights/world" / shading.studio_light)
            self.studio_light_rotate_z = shading.studiolight_rotate_z
            self.studio_light_background_alpha = shading.studiolight_background_alpha
            if hasattr(shading, "studiolight_intensity"):  # parameter added in Blender 2.81
                self.studio_light_intensity = shading.studiolight_intensity


@dataclass(init=False, eq=True)
class ViewLayerSettings:
    """
    Comparable dataclass which holds active view layer settings for ViewportEngine:
    - override material
    """

    material_override: bpy.types.Material = None

    def __init__(self, view_layer: bpy.types.ViewLayer):
        self.material_override = view_layer.material_override


class ViewportEngine(Engine):
    """ Viewport render engine """

    TYPE = 'VIEWPORT'

    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)

        self.gl_texture: gl.GLTexture = None
        self.viewport_settings: ViewportSettings = None
        self.world_settings: world.WorldData = None
        self.shading_data: ShadingData = None
        self.view_layer_data: ViewLayerSettings = None

        self.sync_render_thread: threading.Thread = None
        self.restart_render_event = threading.Event()
        self.render_lock = threading.Lock()
        self.resolve_lock = threading.Lock()

        self.is_finished = False
        self.is_synced = False
        self.is_rendered = False
        self.is_denoised = False
        self.is_resized = False

        self.requested_adapt_ratio = None

        self.render_iterations = 0
        self.render_time = 0

    def stop_render(self):
        self.is_finished = True
        self.restart_render_event.set()
        self.sync_render_thread.join()

        self.rpr_context = None
        self.image_filter = None

    def _resolve(self):
        self.rpr_context.resolve()

    def _do_sync_render(self, depsgraph):
        """
        Thread function for self.sync_render_thread. It always run during viewport render.
        If it doesn't render it waits for self.restart_render_event
        """

        def notify_status(info, status):
            """ Display export progress status """
            wrap_info = textwrap.fill(info, 120)
            self.rpr_engine.update_stats(status, wrap_info)
            log(status, wrap_info)

            # requesting blender to call draw()
            self.rpr_engine.tag_redraw()

        class FinishRender(Exception):
            pass

        try:
            # SYNCING OBJECTS AND INSTANCES
            notify_status("Starting...", "Sync")
            time_begin = time.perf_counter()

            # exporting objects
            material_override = depsgraph.view_layer.material_override
            objects_len = len(depsgraph.objects)
            for i, obj in enumerate(self.depsgraph_objects(depsgraph)):
                if self.is_finished:
                    raise FinishRender

                time_sync = time.perf_counter() - time_begin
                notify_status(f"Time {time_sync:.1f} | Object ({i}/{objects_len}): {obj.name}", "Sync")

                indirect_only = obj.original.indirect_only_get(view_layer=depsgraph.view_layer)
                object.sync(self.rpr_context, obj,
                            indirect_only=indirect_only, material_override=material_override)

            # exporting instances
            instances_len = len(depsgraph.object_instances)
            last_instances_percent = 0

            for i, inst in enumerate(self.depsgraph_instances(depsgraph)):
                if self.is_finished:
                    raise FinishRender

                instances_percent = (i * 100) // instances_len
                if instances_percent > last_instances_percent:
                    time_sync = time.perf_counter() - time_begin
                    notify_status(f"Time {time_sync:.1f} | Instances {instances_percent}%", "Sync")
                    last_instances_percent = instances_percent

                indirect_only = inst.parent.original.indirect_only_get(view_layer=depsgraph.view_layer)
                instance.sync(self.rpr_context, inst,
                              indirect_only=indirect_only, material_override=material_override)

            # shadow catcher
            self.rpr_context.sync_catchers(depsgraph.scene.render.film_transparent)

            self.is_synced = True

            # RENDERING
            notify_status("Starting...", "Render")

            is_adaptive = self.rpr_context.is_aov_enabled(pyrpr.AOV_VARIANCE)

            # Infinite cycle, which starts when scene has to be re-rendered.
            # It waits for restart_render_event be enabled.
            # Exit from this cycle is implemented through raising FinishRender
            # when self.is_finished be enabled from main thread.
            while True:
                self.restart_render_event.wait()

                if self.is_finished:
                    raise FinishRender

                # preparations to start rendering
                iteration = 0
                time_begin = 0.0
                time_render = 0.0
                if is_adaptive:
                    all_pixels = active_pixels = self.rpr_context.width * self.rpr_context.height
                is_last_iteration = False

                # this cycle renders each iteration
                while True:
                    if self.is_finished:
                        raise FinishRender

                    is_adaptive_active = is_adaptive and iteration >= self.rpr_context.get_parameter(
                        pyrpr.CONTEXT_ADAPTIVE_SAMPLING_MIN_SPP)

                    if self.restart_render_event.is_set():
                        # clears restart_render_event, prepares to start rendering
                        self.restart_render_event.clear()
                        iteration = 0

                        if self.is_resized:
                            if not self.rpr_context.gl_interop:
                                # When gl_interop is not enabled, than resize is better to do in
                                # this thread. This is important for hybrid.
                                with self.render_lock:
                                    self.rpr_context.resize(self.viewport_settings.width,
                                                            self.viewport_settings.height)
                            self.is_resized = False

                        self.rpr_context.sync_auto_adapt_subdivision()
                        self.rpr_context.sync_portal_lights()
                        time_begin = time.perf_counter()
                        log(f"Restart render [{self.rpr_context.width}, {self.rpr_context.height}]")

                    # rendering
                    with self.render_lock:
                        if self.restart_render_event.is_set():
                            break

                        self.rpr_context.set_parameter(pyrpr.CONTEXT_FRAMECOUNT, iteration)
                        self.rpr_context.render(restart=(iteration == 0))

                    # resolving
                    with self.resolve_lock:
                        self._resolve()

                    self.is_rendered = True
                    self.is_denoised = False
                    iteration += 1

                    # checking for last iteration
                    # preparing information to show in viewport
                    time_render_prev = time_render
                    time_render = time.perf_counter() - time_begin
                    iteration_time = time_render - time_render_prev
                    if depsgraph.scene.rpr.viewport_limits.adapt_viewport_resolution:
                        if iteration == 2:
                            target_time = 1.0 / depsgraph.scene.rpr.viewport_limits.viewport_samples_per_sec
                            self.requested_adapt_ratio = target_time / iteration_time
                    else:
                        self.requested_adapt_ratio = None

                    if self.render_iterations > 0:
                        info_str = f"Time: {time_render:.1f} sec"\
                                   f" | Iteration: {iteration}/{self.render_iterations}"
                    else:
                        info_str = f"Time: {time_render:.1f}/{self.render_time} sec"\
                                   f" | Iteration: {iteration}"

                    if is_adaptive_active:
                        active_pixels = self.rpr_context.get_info(pyrpr.CONTEXT_ACTIVE_PIXEL_COUNT, int)
                        adaptive_progress = max((all_pixels - active_pixels) / all_pixels, 0.0)
                        info_str += f" | Adaptive Sampling: {math.floor(adaptive_progress * 100)}%"

                    if self.render_iterations > 0:
                        if iteration >= self.render_iterations:
                            is_last_iteration = True
                    else:
                        if time_render >= self.render_time:
                            is_last_iteration = True
                    if is_adaptive and active_pixels == 0:
                        is_last_iteration = True

                    if is_last_iteration:
                        break

                    notify_status(info_str, "Render")

                # notifying viewport that rendering is finished
                if is_last_iteration:
                    time_render = time.perf_counter() - time_begin

                    if self.image_filter:
                        notify_status(f"Time: {time_render:.1f} sec | Iteration: {iteration}"
                                      f" | Denoising...", "Render")

                        # applying denoising
                        with self.resolve_lock:
                            if self.image_filter:
                                self.update_image_filter_inputs()
                                self.image_filter.run()
                                self.is_denoised = True

                        time_render = time.perf_counter() - time_begin
                        notify_status(f"Time: {time_render:.1f} sec | Iteration: {iteration}"
                                      f" | Denoised", "Rendering Done")

                    else:
                        notify_status(f"Time: {time_render:.1f} sec | Iteration: {iteration}",
                                      "Rendering Done")

        except FinishRender:
            log("Finish by user")

        except Exception as e:
            log.error(e, 'EXCEPTION:', traceback.format_exc())
            self.is_finished = True

            # notifying viewport about error
            notify_status(f"{e}.\nPlease see logs for more details.", "ERROR")

        log("Finish _do_sync_render")

    def sync(self, context, depsgraph):
        log('Start sync')

        scene = depsgraph.scene
        viewport_limits = scene.rpr.viewport_limits
        view_layer = depsgraph.view_layer
        settings = get_user_settings()
        use_gl_interop = settings.use_gl_interop and not scene.render.film_transparent

        scene.rpr.init_rpr_context(self.rpr_context, is_final_engine=False,
                                   use_gl_interop=use_gl_interop)

        self.rpr_context.blender_data['depsgraph'] = depsgraph

        self.shading_data = ShadingData(context)
        self.view_layer_data = ViewLayerSettings(view_layer)

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

        if viewport_limits.noise_threshold > 0.0:
            # if adaptive is enable turn on aov and settings
            self.rpr_context.enable_aov(pyrpr.AOV_VARIANCE)
            viewport_limits.set_adaptive_params(self.rpr_context)

        self.rpr_context.scene.set_name(scene.name)

        self.world_settings = self._get_world_settings(depsgraph)
        self.world_settings.export(self.rpr_context)

        rpr_camera = self.rpr_context.create_camera()
        rpr_camera.set_name("Camera")
        self.rpr_context.scene.set_camera(rpr_camera)

        # image filter
        image_filter_settings = view_layer.rpr.denoiser.get_settings(scene, False)
        image_filter_settings['resolution'] = (self.rpr_context.width, self.rpr_context.height)
        self.setup_image_filter(image_filter_settings)

        # other context settings
        self.rpr_context.set_parameter(pyrpr.CONTEXT_PREVIEW, True)
        self.rpr_context.set_parameter(pyrpr.CONTEXT_ITERATIONS, 1)
        scene.rpr.export_render_mode(self.rpr_context)
        scene.rpr.export_ray_depth(self.rpr_context)
        scene.rpr.export_pixel_filter(self.rpr_context)

        self.render_iterations, self.render_time = (viewport_limits.max_samples, 0)

        self.is_finished = False
        self.restart_render_event.clear()

        self.view_mode = context.mode
        self.space_data = context.space_data
        self.sync_render_thread = threading.Thread(target=self._do_sync_render, args=(depsgraph,))
        self.sync_render_thread.start()

        log('Finish sync')

    def sync_update(self, context, depsgraph):
        """ sync just the updated things """

        if not self.is_synced:
            return

        # get supported updates and sort by priorities
        updates = []
        for obj_type in (bpy.types.Scene, bpy.types.World, bpy.types.Material, bpy.types.Object, bpy.types.Collection):
            updates.extend(update for update in depsgraph.updates if isinstance(update.id, obj_type))

        sync_collection = False
        sync_world = False
        is_updated = False
        is_obj_updated = False

        material_override = depsgraph.view_layer.material_override

        shading_data = ShadingData(context)
        if self.shading_data != shading_data:
            sync_world = True

            if self.shading_data.use_scene_lights != shading_data.use_scene_lights:
                sync_collection = True

            self.shading_data = shading_data

        self.rpr_context.blender_data['depsgraph'] = depsgraph

        # if view mode changed need to sync collections
        mode_updated = False
        if self.view_mode != context.mode:
            self.view_mode = context.mode
            mode_updated = True

        with self.render_lock:
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
                    if material.has_uv_map_node(obj):
                        self.remove_material_uvs_instances(obj, depsgraph)

                    mesh_obj = context.object if context.object and \
                                                 context.object.type == 'MESH' else None
                    material.sync_update(self.rpr_context, obj, mesh_obj)
                    is_updated |= self.update_material_on_scene_objects(obj, depsgraph)
                    continue

                if isinstance(obj, bpy.types.Object):
                    if obj.type == 'CAMERA':
                        continue

                    indirect_only = obj.original.indirect_only_get(view_layer=depsgraph.view_layer)
                    active_and_mode_changed = mode_updated and context.active_object == obj.original
                    is_updated |= object.sync_update(self.rpr_context, obj,
                                                     update.is_updated_geometry or active_and_mode_changed, 
                                                     update.is_updated_transform,
                                                     indirect_only=indirect_only,
                                                     material_override=material_override)
                    is_obj_updated |= is_updated
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

            if is_obj_updated:
                with self.resolve_lock:
                    self.rpr_context.sync_catchers()

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

    def _get_render_image(self):
        ''' This is only called for non-GL interop image gets '''
        if utils.IS_MAC:
            with self.render_lock:
                return self.rpr_context.get_image()
        else:
            return self.rpr_context.get_image()

    def draw(self, context):
        log("Draw")

        if not self.is_synced or self.is_finished:
            return

        scene = context.scene

        # initializing self.viewport_settings and requesting first self.restart_render_event
        with self.render_lock:
            if not self.viewport_settings:
                self.viewport_settings = ViewportSettings(context)
                self.viewport_settings.export_camera(self.rpr_context.scene.camera)
                self.restart_render_event.set()

        if not self.is_rendered:
            return

        # drawing functionality
        def draw_(texture_id):
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

        def draw__():
            if self.is_denoised:
                im = None
                with self.resolve_lock:
                    if self.image_filter:
                        im = self.image_filter.get_data()

                if im is not None:
                    self.gl_texture.set_image(im)
                    draw_(self.gl_texture.texture_id)
                    return

            if self.rpr_context.gl_interop:
                with self.resolve_lock:
                    draw_(self.rpr_context.get_frame_buffer().texture_id)
                return

            with self.resolve_lock:
                im = self._get_render_image()

            self.gl_texture.set_image(im)
            draw_(self.gl_texture.texture_id)

        draw__()

        # checking for viewport updates: setting camera position and resizing
        with self.render_lock:
            viewport_settings = ViewportSettings(context)

            if viewport_settings.width * viewport_settings.height == 0:
                return

            if self.requested_adapt_ratio is not None:
                viewport_settings.adapt_resolution(
                    self.requested_adapt_ratio, self.viewport_settings,
                    scene.rpr.viewport_limits.min_resolution_scale)

            if self.viewport_settings != viewport_settings:
                viewport_settings.export_camera(self.rpr_context.scene.camera)
                self.viewport_settings = viewport_settings

                if self.rpr_context.width != viewport_settings.width \
                        or self.rpr_context.height != viewport_settings.height:

                    resolution = (viewport_settings.width, viewport_settings.height)

                    if self.rpr_context.gl_interop:
                        # GL framebuffer ahs to be recreated in this thread,
                        # that's why we call resize here
                        with self.resolve_lock:
                            self.rpr_context.resize(*resolution)

                    if self.gl_texture:
                        self.gl_texture = gl.GLTexture(*resolution)

                    if self.image_filter:
                        image_filter_settings = self.image_filter.settings.copy()
                        image_filter_settings['resolution'] = resolution
                        self.setup_image_filter(image_filter_settings)

                    if self.world_settings.backplate:
                        self.world_settings.backplate.export(self.rpr_context, resolution)

                    self.is_resized = True

                self.restart_render_event.set()

    def sync_objects_collection(self, depsgraph):
        """
        Removes objects which are not present in depsgraph anymore.
        Adds objects which are not present in rpr_context but existed in depsgraph
        """
        res = False
        view_layer_data = ViewLayerSettings(depsgraph.view_layer)
        material_override = view_layer_data.material_override

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

        if object_keys_to_remove:
            log("Object keys to remove", object_keys_to_remove)
            for obj_key in object_keys_to_remove:
                if obj_key in self.rpr_context.objects:
                    self.rpr_context.remove_object(obj_key)
                    res = True

        if object_keys_to_export:
            log("Object keys to add", object_keys_to_export)

            res |= self.sync_collection_objects(depsgraph, object_keys_to_export,
                                                material_override)

            res |= self.sync_collection_instances(depsgraph, object_keys_to_export,
                                                  material_override)

        # update/remove material override on rest of scene object
        if view_layer_data != self.view_layer_data:
            # update/remove material override on all other objects
            self.view_layer_data = view_layer_data
            res = True

            rpr_mesh_keys = set(key for key, obj in self.rpr_context.objects.items()
                                if isinstance(obj, pyrpr.Mesh) and obj.is_visible)
            unchanged_meshes_keys = tuple(e for e in depsgraph_keys if e in rpr_mesh_keys)
            log("Object keys to update material override", unchanged_meshes_keys)
            self.sync_collection_objects(depsgraph, unchanged_meshes_keys,
                                         material_override)

            self.sync_collection_instances(depsgraph, unchanged_meshes_keys,
                                           material_override)

        return res

    def sync_collection_objects(self, depsgraph, object_keys_to_export, material_override):
        """ Export collections objects """
        res = False

        for obj in self.depsgraph_objects(depsgraph):
            obj_key = object.key(obj)
            if obj_key not in object_keys_to_export:
                continue

            rpr_obj = self.rpr_context.objects.get(obj_key, None)
            if rpr_obj:
                rpr_obj.set_visibility(True)

                if not material_override:
                    rpr_obj.set_material(None)
                assign_materials(self.rpr_context, rpr_obj, obj, material_override)
                res = True
            else:
                indirect_only = obj.original.indirect_only_get(view_layer=depsgraph.view_layer)
                object.sync(self.rpr_context, obj,
                            indirect_only=indirect_only, material_override=material_override)

                res = True
        return res

    def sync_collection_instances(self, depsgraph, object_keys_to_export, material_override):
        """ Export collections instances """
        res = False

        for inst in self.depsgraph_instances(depsgraph):
            instance_key = instance.key(inst)
            if instance_key not in object_keys_to_export:
                continue

            if not material_override:
                inst_obj = self.rpr_context.objects.get(instance_key, None)
                if inst_obj:
                    if len(inst.object.material_slots) == 0:
                        # remove override from instance without assigned materials
                        inst_obj.set_material(None)
                    assign_materials(self.rpr_context, inst_obj, inst.object)
                    res = True
            else:
                indirect_only = inst.parent.original.indirect_only_get(view_layer=depsgraph.view_layer)
                instance.sync(self.rpr_context, inst,
                              indirect_only=indirect_only, material_override=material_override)
                res = True
        return res

    def remove_material_uvs_instances(self, mat, depsgraph):
        """ Find and remove each unique instance of material by UVs combinations """
        uvs = set(entry.data.rpr.uv_sets_names for entry in self.depsgraph_objects(depsgraph)
                  if isinstance(entry, bpy.types.Mesh) and mat.name in entry.material_slots)

        for entry in uvs:
            for socket in ('Surface', 'Volume', 'Displacement'):
                mat_key = material.key((mat.name, entry), input_socket_key=socket)
                if mat_key in self.rpr_context.materials:
                    self.rpr_context.remove_material(mat_key)

    def update_material_on_scene_objects(self, mat, depsgraph):
        """ Find all mesh material users and reapply material """
        material_override = depsgraph.view_layer.material_override

        if material_override and material_override.name == mat.name:
            objects = self.depsgraph_objects(depsgraph)
            active_mat = material_override
        else:
            objects = tuple(obj for obj in self.depsgraph_objects(depsgraph)
                            if mat.name in obj.material_slots.keys())
            active_mat = mat

        updated = False
        for obj in objects:
            rpr_material = material.sync(self.rpr_context, active_mat, obj=obj)
            rpr_volume = material.sync(self.rpr_context, active_mat, 'Volume', obj=obj)
            rpr_displacement = material.sync(self.rpr_context, active_mat, 'Displacement', obj=obj)

            if not rpr_material and not rpr_volume and not rpr_displacement:
                continue

            indirect_only = obj.original.indirect_only_get(view_layer=depsgraph.view_layer)

            if object.key(obj) not in self.rpr_context.objects:
                object.sync(self.rpr_context, obj, indirect_only=indirect_only)
                updated = True
                continue

            updated |= object.sync_update(self.rpr_context, obj, False, False,
                                          indirect_only=indirect_only, material_override=material_override)

        return updated

    def update_render(self, scene: bpy.types.Scene, view_layer: bpy.types.ViewLayer):
        ''' update settings if changed while live returns True if restart needed '''
        restart = scene.rpr.export_render_mode(self.rpr_context)
        restart |= scene.rpr.export_ray_depth(self.rpr_context)
        restart |= scene.rpr.export_pixel_filter(self.rpr_context)

        render_iterations, render_time = (scene.rpr.viewport_limits.max_samples, 0)

        if self.render_iterations != render_iterations or self.render_time != render_time:
            self.render_iterations = render_iterations
            self.render_time = render_time
            restart = True

        restart |= scene.rpr.viewport_limits.set_adaptive_params(self.rpr_context)

        # image filter
        image_filter_settings = view_layer.rpr.denoiser.get_settings(scene, False)
        image_filter_settings['resolution'] = (self.rpr_context.width, self.rpr_context.height)
        if self.setup_image_filter(image_filter_settings):
            self.is_denoised = False
            restart = True

        return restart

    def setup_image_filter(self, settings):
        with self.resolve_lock:
            return super().setup_image_filter(settings)

    def _enable_image_filter(self, settings):
        super()._enable_image_filter(settings)

        if not self.gl_texture:
            self.gl_texture = gl.GLTexture(self.rpr_context.width, self.rpr_context.height)

    def _get_world_settings(self, depsgraph):
        if self.shading_data.use_scene_world:
            return world.WorldData.init_from_world(depsgraph.scene.world)

        return world.WorldData.init_from_shading_data(self.shading_data)

    def depsgraph_objects(self, depsgraph, with_camera=False):
        for obj in super().depsgraph_objects(depsgraph, with_camera):
            if obj.type == 'LIGHT' and not self.shading_data.use_scene_lights:
                continue
            
            # check for local view visability
            if not obj.visible_in_viewport_get(self.space_data):
                continue

            yield obj

    def depsgraph_instances(self, depsgraph):
        for instance in super().depsgraph_instances(depsgraph):
            # check for local view visability
            if not instance.parent.visible_in_viewport_get(self.space_data):
                continue

            yield instance
        

from .context import RPRContext2

class ViewportEngine2(ViewportEngine):
    _RPRContext = RPRContext2
