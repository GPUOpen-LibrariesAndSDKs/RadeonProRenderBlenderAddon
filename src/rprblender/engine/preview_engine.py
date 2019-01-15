import numpy as np
import bpy

import pyrpr
from rprblender import utils
from .engine import Engine
from rprblender.properties import SyncError

from rprblender.utils import logging
log = logging.Log(tag='PreviewEngine')


class PreviewEngine(Engine):
    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)
        self.is_synced = False
        self.render_iterations = 0

    def render(self):
        if not self.is_synced:
            return

        log("Start render")

        result = self.rpr_engine.begin_result(0, 0, self.rpr_context.width, self.rpr_context.height)

        self.rpr_context.clear_frame_buffers()
        self.rpr_context.set_parameter('iterations', self.render_iterations)
        self.rpr_context.render()

        self.rpr_context.resolve()
        self.set_render_result(result.layers[0].passes)
        self.rpr_engine.end_result(result)

        log('Finish render')

    def sync(self, depsgraph):
        log('Start syncing')
        self.is_synced = False

        self._sync_render(depsgraph.scene)

        # getting visible objects
        for i, obj_instance in enumerate(depsgraph.object_instances):
            obj = obj_instance.object
            try:
                obj.rpr.sync(self.rpr_context, obj_instance)
            except SyncError as e:
                log.warn(e, "Skipping")

        self.rpr_context.scene.set_camera(self.rpr_context.objects[utils.key(depsgraph.scene.camera)])
        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)
        self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)

        self.rpr_context.set_parameter('preview', False)

        self.is_synced = True
        log('Finish sync')

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

        width = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
        height = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)

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

        self.rpr_context.set_parameter('raycastepsilon', rpr.ray_cast_epsilon * 0.001) # Convert millimeters to meters

        self.render_iterations = rpr.viewport_limits.iterations
