import threading
import time

import bpy
import bgl

import pyrpr
from .engine import Engine
from rprblender.properties import SyncError
from rprblender.export import camera, material, world, object, instance
from rprblender.utils import gl
from rprblender import config

from rprblender.utils import logging
log = logging.Log(tag='ViewportEngine')


class ViewportEngine(Engine):
    """ Viewport render engine """

    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)
        self.is_synced = False
        self.render_iterations = 0
        self.render_time = 0
        self.noise_threshold = 0.0
        self.gl_texture: gl.GLTexture = None

        self.camera_settings = {}
        self.world_settings = None

        self.render_thread: threading.Thread = None
        self.resolve_thread: threading.Thread = None
        self.restart_render_event = threading.Event()
        self.render_event = threading.Event()
        self.finish_render = False
        self.rpr_context.is_preview = True

    def render(self):
        self.finish_render = False

        self.restart_render_event.clear()
        self.render_event.clear()

        self.render_thread = threading.Thread(target=ViewportEngine._do_render, args=(self,))
        self.render_thread.start()

        self.resolve_thread = threading.Thread(target=ViewportEngine._do_resolve, args=(self,))
        self.resolve_thread.start()

    def stop_render(self):
        if not self.render_thread:
            return

        self.finish_render = True
        self.restart_render_event.set()
        self.render_thread.join()

        self.render_event.set()
        self.resolve_thread.join()

    def notify_status(self, info):
        self.rpr_engine.update_stats("", info)

    def _do_render(self):
        """
        Thread function for self.render_thread. It always run during viewport render.
        If it doesn't render it waits for self.restart_render_event
        """

        log("Start render thread")
        while True:
            self.restart_render_event.wait()

            if self.finish_render:
                break

            iteration = 0
            time_begin = 0.0
            time_render = 0.0

            while True:
                if self.finish_render:
                    break

                if self.restart_render_event.is_set():
                    self.restart_render_event.clear()
                    iteration = 0
                    self.rpr_context.sync_auto_adapt_subdivision()
                    self.rpr_context.sync_portal_lights()
                    time_begin = time.perf_counter()
                    log("Restart render")

                log("Render iteration: %d / %d" % (iteration, self.render_iterations))

                self.rpr_context.render(restart=(iteration == 0))

                self.render_event.set()

                iteration += 1
                time_render = time.perf_counter() - time_begin

                if self.render_iterations > 0:
                    self.notify_status("Time: %.1f sec | Iteration: %d/%d" % (time_render, iteration, self.render_iterations))
                    if iteration >= self.render_iterations:
                        break
                else:
                    self.notify_status("Time: %.1f/%d sec | Iteration: %d" % (time_render, self.render_time, iteration))
                    if time_render >= self.render_time:
                        break

            self.notify_status("Rendering Done | Time: %.1f sec | Iteration: %d" % (time_render, iteration))

        log("Finish render thread")

    def _do_resolve(self):
        """
        Thread function for self.resolve_thread. It only resolves rendered frame buffers
        It always run during viewport render. It waits for self.render_event
        """

        log("Start resolve thread")
        while True:
            self.render_event.wait()
            self.render_event.clear()

            if self.finish_render:
                break

            self.rpr_context.resolve()
            self.rpr_context.resolve_extras()

            self.rpr_engine.tag_redraw()

        log("Finish resolve thread")

    def get_viewport_resolution(self, context):
        ''' Gets the viewport resolution.  If limit is turned on,
            scales the region resolution down to max of a given resolution with the same 
            aspect ratio as the region, returns scaled resolution'''
        scene = context.depsgraph.scene

        region_w,region_h = (context.region.width, context.region.height)
        if not scene.rpr.viewport_limits.limit_viewport_resolution:
            # simply return region width/height
            return region_w,region_h

        # else we have to scale
        render_w = int(scene.render.resolution_x * scene.render.resolution_percentage / 100.0)
        render_h = int(scene.render.resolution_y * scene.render.resolution_percentage / 100.0)
            
        region_aspect = region_w/region_h
        render_aspect = render_w/render_h

        if render_aspect > region_aspect:
            # if render resolution is wider, use the max height from render and scale to aspect ratio
            region_h = min(render_h, region_h)
            region_w = int(region_aspect * region_h)
        else:
            # scale to render width and maintain aspect ratio
            region_w = min(render_w, region_w)
            region_h = int(region_w / region_aspect)

        return region_w, region_h


    def sync(self, context):
        log('Start sync')
    
        depsgraph = context.depsgraph
        scene = depsgraph.scene
        viewport_limits = scene.rpr.viewport_limits

        scene.rpr.init_rpr_context(self.rpr_context, is_final_engine=False, use_gl_interop=config.use_gl_interop)
        
        w,h = self.get_viewport_resolution(context)
        self.rpr_context.resize(w, h)
        
        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)
        self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)

        self.noise_threshold = viewport_limits.noise_threshold
        if self.noise_threshold > 0.0:
            # if adaptive is enable turn on aov and settings
            self.rpr_context.enable_aov(pyrpr.AOV_VARIANCE)
            viewport_limits.set_adaptive_params(self.rpr_context)

        self.world_settings = world.WorldData(scene.world)
        world.sync(self.rpr_context, scene.world)

        self.rpr_context.scene.set_name(scene.name)

        rpr_camera = self.rpr_context.create_camera()
        rpr_camera.set_name("Camera")
        self.rpr_context.scene.set_camera(rpr_camera)

        # exporting objects
        for obj in self.depsgraph_objects(depsgraph):
            try:
                object.sync(self.rpr_context, obj)

            except SyncError as e:
                log.warn("Object syncing error", e)

        # exporting instances
        for inst in self.depsgraph_instances(depsgraph):
            try:
                instance.sync(self.rpr_context, inst)

            except SyncError as e:
                log.warn("Instance syncing error", e)

        if not self.rpr_context.gl_interop:
            self.gl_texture = gl.GLTexture(w, h)

        self.rpr_context.sync_shadow_catcher()

        self.rpr_context.set_parameter('preview', True)
        self.rpr_context.set_parameter('iterations', 1)
        scene.rpr.export_ray_depth(self.rpr_context)

        self.render_iterations, self.render_time = (viewport_limits.max_samples, 0) 

        self.is_synced = True
        log('Finish sync')

    def sync_update(self, context):
        """ sync just the updated things """

        depsgraph = context.depsgraph

        # get supported updates and sort by priorities
        updates = []
        for obj_type in (bpy.types.Scene, bpy.types.World, bpy.types.Material, bpy.types.Object, bpy.types.Collection):
            updates.extend(update for update in depsgraph.updates if isinstance(update.id, obj_type))

        if not updates:
            return

        is_updated = False

        with self.rpr_context.lock:
            sync_collection = False

            for update in updates:
                obj = update.id
                log("sync_update", obj)
                if isinstance(obj, bpy.types.Scene):
                    is_updated |= self.update_render(obj)

                    # Outliner object visibilty change will provide us only bpy.types.Scene update
                    # That's why we need to sync objects collection in the end
                    sync_collection = True

                    continue

                if isinstance(obj, bpy.types.Material):
                    is_updated |= material.sync_update(self.rpr_context, obj)
                    continue

                if isinstance(obj, bpy.types.Object):
                    if obj.type == 'CAMERA':
                        continue

                    is_updated |= object.sync_update(self.rpr_context, obj, update.is_updated_geometry, update.is_updated_transform)
                    continue

                if isinstance(obj, bpy.types.World):
                    world_settings = world.WorldData(obj)
                    if world_settings == self.world_settings:
                        continue

                    is_updated |= world.sync_update(self.rpr_context, obj, self.world_settings, world_settings)
                    self.world_settings = world_settings
                    continue

                if isinstance(obj, bpy.types.Collection):
                    sync_collection = True
                    continue

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

    def draw(self, context):
        log("Draw")

        camera_settings = camera.CameraData.init_from_context(context)
        width, height = self.get_viewport_resolution(context)
        scene = context.depsgraph.scene

        is_camera_update = self.camera_settings != camera_settings
        is_resize_update = self.rpr_context.width != width or self.rpr_context.height != height

        if is_camera_update or is_resize_update:
            with self.rpr_context.lock:
                if is_camera_update:
                    self.camera_settings = camera_settings
                    self.camera_settings.export(self.rpr_context.scene.camera)

                if is_resize_update:
                    self.rpr_context.resize(width, height)
                    if not self.rpr_context.gl_interop:
                        self.gl_texture = gl.GLTexture(width, height)

            self.restart_render_event.set()

        if self.rpr_context.gl_interop:
            texture_id = self.rpr_context.get_frame_buffer(pyrpr.AOV_COLOR).texture_id
        else:
            im = self.rpr_context.get_image(pyrpr.AOV_COLOR)
            self.gl_texture.set_image(im)
            texture_id = self.gl_texture.texture_id

        # Bind shader that converts from scene linear to display space,
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE_MINUS_SRC_ALPHA)
        self.rpr_engine.bind_display_space_shader(scene)

        # note this has to draw to region size, not scaled down size
        self._draw_texture(texture_id, 0, 0, context.region.width, context.region.height)

        self.rpr_engine.unbind_display_space_shader()
        bgl.glDisable(bgl.GL_BLEND)

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

        # set of rpr object keys except environment lights
        rpr_object_keys = self.rpr_context.objects.keys() - world.ENVIRONMENT_LIGHTS_NAMES

        # sets of objetcs keys to remove from rpr
        object_keys_to_remove = rpr_object_keys - depsgraph_keys

        # sets of objetcs keys to export into rpr
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
                if object.key(obj) not in object_keys_to_export:
                    continue

                try:
                    object.sync(self.rpr_context, obj)
                    res = True

                except SyncError as e:
                    log.warn("Object syncing error", e)

            # exporting instances
            for inst in self.depsgraph_instances(depsgraph):
                if instance.key(inst) not in object_keys_to_export:
                    continue

                try:
                    instance.sync(self.rpr_context, inst)
                    res = True

                except SyncError as e:
                    log.warn("Instance syncing error", e)

        return res

    def update_render(self, scene: bpy.types.Scene):
        ''' update settings if changed while live returns True if restart needed'''
        restart = scene.rpr.export_ray_depth(self.rpr_context)

        render_iterations, render_time = (scene.rpr.viewport_limits.max_samples, 0)

        if self.render_iterations != render_iterations or self.render_time != render_time:
            self.render_iterations = render_iterations
            self.render_time = render_time
            restart = True

        noise_threshold = scene.rpr.viewport_limits.noise_threshold
        if noise_threshold != self.noise_threshold:
            # only update settings if changed
            scene.rpr.viewport_limits.set_adaptive_params(self.rpr_context)
            self.noise_threshold = noise_threshold
            restart = True

        return restart

    def depsgraph_objects(self, depsgraph: bpy.types.Depsgraph):
        """ Iterates over super().depsgraph_objects() and excludes cameras """

        for obj in super().depsgraph_objects(depsgraph):
            if obj.type != 'CAMERA':
                yield obj

    def depsgraph_instances(self, depsgraph: bpy.types.Depsgraph):
        """ Iterates over super().depsgraph_instances() and excludes cameras """

        for instance in super().depsgraph_instances(depsgraph):
            if instance.object.type != 'CAMERA':
                yield instance
