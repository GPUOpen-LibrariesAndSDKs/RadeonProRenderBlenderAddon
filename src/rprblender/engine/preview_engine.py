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

        scene = depsgraph.scene
        settings_scene = bpy.context.scene

        settings_scene.rpr.sync(self.rpr_context)
        self.rpr_context.resize(scene.render.resolution_x, scene.render.resolution_y)

        # getting visible objects
        for i, obj_instance in enumerate(depsgraph.object_instances):
            obj = obj_instance.object
            try:
                obj.rpr.sync(self.rpr_context, obj_instance, motion_blur_info=None)
            except SyncError as e:
                log.warn(e, "Skipping")

        self.rpr_context.scene.set_name(scene.name)
        self.rpr_context.scene.set_camera(self.rpr_context.objects[utils.key(depsgraph.scene.camera)])
        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)
        self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)

        self.rpr_context.set_parameter('preview', False)

        self.render_iterations = settings_scene.rpr.viewport_limits.iterations

        self.is_synced = True
        log('Finish sync')
