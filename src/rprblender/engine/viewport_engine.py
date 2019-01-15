import threading
import numpy as np

import bpy
from gpu_extras.presets import draw_texture_2d

import pyrpr
from .engine import Engine
from rprblender.properties import SyncError
import rprblender.utils.camera as camera_ut

from rprblender.utils import logging
log = logging.Log(tag='ViewportEngine')


class ViewportEngine(Engine):
    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)
        self.is_synced = False
        self.render_iterations = 0
        self.gl_texture: int = None

        self.camera_settings = {}
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

                    self.rpr_context.render()

                self.render_event.set()

                iteration += 1

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

    def sync(self, depsgraph):
        log('Start sync')

        scene = depsgraph.scene

        self._sync_render(scene)
        scene.world.rpr.sync(self.rpr_context)

        # getting visible objects
        for i, obj_instance in enumerate(depsgraph.object_instances):
            obj = obj_instance.object
            if obj.type == 'CAMERA':
                continue

            try:
                obj.rpr.sync(self.rpr_context, obj_instance)
            except SyncError as e:
                log.warn(e, "Skipping")

        rpr_camera = self.rpr_context.create_camera('VIEWPORT_CAMERA')
        rpr_camera.set_name("Camera")
        self.rpr_context.scene.set_camera(rpr_camera)

        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)
        self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)

        self.rpr_context.set_parameter('preview', True)
        self.rpr_context.set_parameter('iterations', 1)

        self.gl_texture = self.rpr_context.get_frame_buffer(pyrpr.AOV_COLOR).gl_texture
        self.is_synced = True
        log('Finish sync')

    def sync_updated(self, depsgraph):
        ''' sync just the updated things '''
        log("Start sync_updated")

        for updated_obj in depsgraph.updates:
            log("updated {}; geometry updated {}; transform updated {}".format(
                updated_obj.id.name, updated_obj.is_updated_geometry, updated_obj.is_updated_transform))

        log("Finish sync_updated")

    def draw(self, context):
        log("Draw")

        camera_settings = camera_ut.get_viewport_camera_settings(context)
        if self.camera_settings != camera_settings:
            self.camera_settings = camera_settings
            with self.render_lock:
                camera_ut.set_camera_settings(self.rpr_context.scene.camera, self.camera_settings)

            self.restart_render_event.set()

        draw_texture_2d(self.gl_texture, (0, 0), self.rpr_context.width, self.rpr_context.height)


    def _sync_render(self, scene):
        log("sync_render", scene)

        rpr = bpy.context.scene.rpr     # getting rpr settings from user's scene

        context_flags = 0
        context_props = []
        if rpr.devices in ['CPU', 'GPU+CPU']:
            context_flags |= pyrpr.Context.cpu_device['flag']
            context_props.extend([pyrpr.CONTEXT_CREATEPROP_CPU_THREAD_LIMIT, rpr.cpu_threads])
        if rpr.devices in ['GPU', 'GPU+CPU']:
            for i, gpu_state in enumerate(rpr.gpu_states):
                if gpu_state:
                    context_flags |= pyrpr.Context.gpu_devices[i]['flag']

            # enabling GL interop
            context_flags |= pyrpr.CREATION_FLAGS_ENABLE_GL_INTEROP

        width = bpy.context.region.width
        height = bpy.context.region.height

        context_props.append(0) # should be followed by 0
        self.rpr_context.init(width, height, context_flags, context_props)
        self.rpr_context.scene.set_name(scene.name)

        # set light paths values
        self.rpr_context.set_parameter('maxRecursion', rpr.max_ray_depth)
        self.rpr_context.set_parameter('maxdepth.diffuse', rpr.diffuse_depth)
        self.rpr_context.set_parameter('maxdepth.glossy', rpr.glossy_depth)
        self.rpr_context.set_parameter('maxdepth.shadow', rpr.shadow_depth)
        self.rpr_context.set_parameter('maxdepth.refraction', rpr.refraction_depth)
        self.rpr_context.set_parameter('maxdepth.refraction.glossy', rpr.glossy_refraction_depth)
        self.rpr_context.set_parameter('radianceclamp', rpr.clamp_radiance if rpr.use_clamp_radiance else np.finfo(np.float32).max)

        self.rpr_context.set_parameter('raycastepsilon', rpr.ray_cast_epsilon * 0.001)  # Convert millimeters to meters

        self.render_iterations = rpr.viewport_limits.iterations
