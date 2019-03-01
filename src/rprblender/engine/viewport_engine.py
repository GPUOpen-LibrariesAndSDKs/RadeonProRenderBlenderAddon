import threading
import time

import bpy
from gpu_extras.presets import draw_texture_2d

import pyrpr
from .engine import Engine
from rprblender.properties import SyncError
from rprblender.export import camera, material, world, object, key
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
        self.gl_texture: gl.GLTexture = None

        self.camera_settings = {}
        self.world_settings = None

        self.render_lock = threading.Lock()
        self.render_thread: threading.Thread = None
        self.resolve_thread: threading.Thread = None
        self.restart_render_event = threading.Event()
        self.render_event = threading.Event()
        self.finish_render = False

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

            while True:
                if self.finish_render:
                    break

                if self.restart_render_event.is_set():
                    self.restart_render_event.clear()
                    iteration = 0
                    time_begin = time.perf_counter()
                    log("Restart render")

                log("Render iteration: %d / %d" % (iteration, self.render_iterations))

                with self.render_lock:
                    if iteration == 0:
                        self.rpr_context.clear_frame_buffers()
                        self.rpr_context.sync_auto_adapt_subdivision()

                    self.rpr_context.render()

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

            with self.render_lock:
                self.rpr_context.resolve()

            self.rpr_context.resolve_extras()

            self.rpr_engine.tag_redraw()

        log("Finish resolve thread")

    def sync(self, context):
        log('Start sync')

        depsgraph = context.depsgraph
        scene = depsgraph.scene

        scene.rpr.init_rpr_context(self.rpr_context, is_final_engine=False, use_gl_interop=config.use_gl_interop)
        self.rpr_context.resize(context.region.width, context.region.height)

        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)
        self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)

        self.world_settings = world.WorldData(scene.world)
        world.sync(self.rpr_context, scene.world)

        self.rpr_context.scene.set_name(scene.name)

        rpr_camera = self.rpr_context.create_camera()
        rpr_camera.set_name("Camera")
        self.rpr_context.scene.set_camera(rpr_camera)

        # getting visible objects
        for obj_instance in depsgraph.object_instances:
            obj = obj_instance.object
            if obj.type == 'CAMERA':
                continue

            try:
                object.sync(self.rpr_context, obj, obj_instance, motion_blur_info=None)
            except SyncError as e:
                log.warn(e, "Skipping")

        if not self.rpr_context.gl_interop:
            self.gl_texture = gl.GLTexture(self.rpr_context.width, self.rpr_context.height)

        self.rpr_context.sync_shadow_catcher()

        self.rpr_context.set_parameter('preview', True)
        self.rpr_context.set_parameter('iterations', 1)
        scene.rpr.export_ray_depth(self.rpr_context)

        self.render_iterations, self.render_time = \
            (scene.rpr.viewport_limits.iterations, 0) if scene.rpr.viewport_limits.type == 'ITERATIONS' else \
            (0, scene.rpr.viewport_limits.seconds)

        self.is_synced = True
        log('Finish sync')

    def sync_update(self, context):
        """ sync just the updated things """
        depsgraph = context.depsgraph

        # get supported updates and sort by priorities
        updates = []
        for obj_type in (bpy.types.Scene, bpy.types.World, bpy.types.Material, bpy.types.Object, bpy.types.Collection):
            updates.extend(update for update in depsgraph.updates if isinstance(update.id, obj_type))

        is_updated = False

        with self.render_lock:
            for update in updates:
                obj = update.id
                log("sync_update", obj)
                if isinstance(obj, bpy.types.Scene):
                    is_updated |= self.update_render(obj)
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
                    # Here we need only remove deleted objects. Additional objects should be already added before
                    is_updated |= self.remove_deleted_objects(depsgraph.object_instances)
                    continue

                # TODO: sync_update for other object types

        if is_updated:
            self.restart_render_event.set()

    def draw(self, context):
        log("Draw")

        camera_settings = camera.CameraData.init_from_context(context)
        width = context.region.width
        height = context.region.height

        is_camera_update = self.camera_settings != camera_settings
        is_resize_update = self.rpr_context.width != width or self.rpr_context.height != height

        if is_camera_update or is_resize_update:
            with self.render_lock:
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

        draw_texture_2d(texture_id, (0, 0), self.rpr_context.width, self.rpr_context.height)

    def remove_deleted_objects(self, obj_instances):

        keys = set(key(obj_instance) for obj_instance in obj_instances)

        res = False
        for obj_key in tuple(self.rpr_context.objects.keys()):
            if obj_key == world.IBL_LIGHT_NAME:
                continue

            if obj_key not in keys:
                self.rpr_context.remove_object(obj_key)
                res = True

        return res

    def update_render(self, scene: bpy.types.Scene):
        res = scene.rpr.export_ray_depth(self.rpr_context)

        render_iterations, render_time = \
            (scene.rpr.viewport_limits.iterations, 0) if scene.rpr.viewport_limits.type == 'ITERATIONS' else \
            (0, scene.rpr.viewport_limits.seconds)

        if self.render_iterations != render_iterations or self.render_time != render_time:
            self.render_iterations = render_iterations
            self.render_time = render_time
            res = True

        return res
