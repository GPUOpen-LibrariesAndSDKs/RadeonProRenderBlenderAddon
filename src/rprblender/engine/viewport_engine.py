import threading

import bpy
from gpu_extras.presets import draw_texture_2d

import pyrpr
from .engine import Engine
from rprblender.properties import SyncError
import rprblender.utils.camera as camera_ut
import rprblender.utils.world as world_ut
from rprblender.utils import gl
from rprblender import utils

from rprblender.utils import logging
log = logging.Log(tag='ViewportEngine')


class ViewportEngine(Engine):
    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)
        self.is_synced = False
        self.render_iterations = 0
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
        log("Start render thread")
        while True:
            self.restart_render_event.wait()

            if self.finish_render:
                break

            iteration = 0
            while iteration < self.render_iterations:
                if self.finish_render:
                    break

                if self.restart_render_event.is_set():
                    self.restart_render_event.clear()
                    iteration = 0
                    log("Restart render")

                log("Render iteration: %d / %d" % (iteration, self.render_iterations))

                with self.render_lock:
                    if iteration == 0:
                        self.rpr_context.clear_frame_buffers()
                        self.rpr_context.sync_auto_adapt_subdivision()

                    self.rpr_context.render()

                self.render_event.set()

                iteration += 1

                self.notify_status("Iteration: %d/%d" % (iteration, self.render_iterations))

            self.notify_status("Rendering Done")

        log("Finish render thread")

    def _do_resolve(self):
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

        scene.rpr.sync(self.rpr_context, use_gl_interop=True)
        self.rpr_context.resize(context.region.width, context.region.height)

        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)
        self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)

        self.world_settings = world_ut.get_world_data(scene.world)
        scene.world.rpr.sync(self.rpr_context)

        self.rpr_context.scene.set_name(scene.name)

        rpr_camera = self.rpr_context.create_camera('VIEWPORT_CAMERA')
        rpr_camera.set_name("Camera")
        self.rpr_context.scene.set_camera(rpr_camera)

        # getting visible objects
        for obj_instance in depsgraph.object_instances:
            obj = obj_instance.object
            if obj.type == 'CAMERA':
                continue

            try:
                obj.rpr.sync(self.rpr_context, obj_instance)
            except SyncError as e:
                log.warn(e, "Skipping")

        if not self.rpr_context.gl_interop:
            self.gl_texture = gl.GLTexture(self.rpr_context.width, self.rpr_context.height)

        self.rpr_context.sync_shadow_catcher()

        self.rpr_context.set_parameter('preview', True)
        self.rpr_context.set_parameter('iterations', 1)

        self.render_iterations = scene.rpr.viewport_limits.iterations

        self.is_synced = True
        log('Finish sync')

    def sync_update(self, context):
        ''' sync just the updated things '''
        log("sync_update")
        depsgraph = context.depsgraph

        is_updated = False

        with self.render_lock:
            for update in depsgraph.updates:
                obj = update.id
                if isinstance(obj, bpy.types.Scene):
                    # TODO: update scene settings
                    continue

                elif isinstance(obj, bpy.types.Object):
                    if obj.type == 'CAMERA':
                        continue

                    is_updated |= obj.rpr.sync_update(self.rpr_context, update.is_updated_geometry, update.is_updated_transform)

                elif isinstance(obj, bpy.types.World):
                    world_settings = world_ut.get_world_data(obj)
                    if world_settings != self.world_settings:
                        old_settings = self.world_settings
                        self.world_settings = world_settings
                        obj.rpr.sync_update(self.rpr_context, old_settings, self.world_settings)

                        is_updated |= True

                elif isinstance(obj, bpy.types.Collection):
                    # updating objects collection
                    is_updated |= self.sync_update_collection(depsgraph.object_instances)

                else:
                    # TODO: sync_update for other object types
                    continue

        if is_updated:
            self.restart_render_event.set()

    def draw(self, context):
        log("Draw")

        camera_settings = camera_ut.get_viewport_camera_data(context)
        if self.camera_settings != camera_settings:
            self.camera_settings = camera_settings
            with self.render_lock:
                camera_ut.set_camera_data(self.rpr_context.scene.camera, self.camera_settings)

            self.restart_render_event.set()

        width = context.region.width
        height = context.region.height

        if self.rpr_context.width != width or self.rpr_context.height != height:
            with self.render_lock:
                self.rpr_context.resize(width, height)
                if not self.rpr_context.gl_interop:
                    self.gl_texture = gl.GLTexture(width, height)

            self.restart_render_event.set()

        # TODO: Setting camera and resize should move to sync() and sync_update()

        if self.rpr_context.gl_interop:
            texture_id = self.rpr_context.get_frame_buffer(pyrpr.AOV_COLOR).texture_id
        else:
            im = self.rpr_context.get_image(pyrpr.AOV_COLOR)
            self.gl_texture.set_image(im)
            texture_id = self.gl_texture.texture_id

        draw_texture_2d(texture_id, (0, 0), self.rpr_context.width, self.rpr_context.height)

    def sync_update_collection(self, obj_instances):
        result = False
        keys = set()
        for obj_instance in obj_instances:
            obj = obj_instance.object
            if obj.type == 'CAMERA':
                continue

            key = utils.key(obj_instance)
            keys.add(key)
            if key in self.rpr_context.objects:
                continue

            try:
                obj.rpr.sync(self.rpr_context, obj_instance)
                result = True
            except SyncError as e:
                log.warn(e, "Skipping")

        for key in tuple(self.rpr_context.objects.keys()):
            if key in ('VIEWPORT_CAMERA', world_ut.IBL_LIGHT_NAME):
                continue

            if key not in keys:
                self.rpr_context.remove_object(key)
                result = True

        return result
