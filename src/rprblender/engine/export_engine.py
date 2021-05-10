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
"""
Scene export to file
"""
import math

import pyrpr_load_store

from rprblender.export import (
    instance,
    object,
    particle,
    world,
    camera
)
from .context import RPRContext, RPRContext2
from .engine import Engine
import pyrpr

from rprblender.utils.logging import Log
log = Log(tag='ExportEngine')


class ExportEngine(Engine):
    TYPE = 'EXPORT'

    def __init__(self):
        self.rpr_context = RPRContext()
        self.rpr_context.engine_type = self.TYPE

    def sync(self, context):
        """ Prepare scene for export """
        log('Start sync')

        depsgraph = context.evaluated_depsgraph_get()
        self.rpr_context.blender_data['depsgraph'] = depsgraph
        scene = depsgraph.scene

        use_contour = scene.rpr.is_contour_used()

        scene.rpr.init_rpr_context(self.rpr_context, use_contour_integrator=use_contour)

        self.rpr_context.scene.set_name(scene.name)
        self.rpr_context.width = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
        self.rpr_context.height = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)

        world.sync(self.rpr_context, scene.world)

        # camera, objects, particles
        for obj in self.depsgraph_objects(depsgraph, with_camera=True):
            indirect_only = obj.original.indirect_only_get(view_layer=depsgraph.view_layer)
            object.sync(self.rpr_context, obj, indirect_only=indirect_only,
                        frame_current=scene.frame_current)

        # instances
        for inst in self.depsgraph_instances(depsgraph):
            indirect_only = inst.parent.original.indirect_only_get(view_layer=depsgraph.view_layer)
            instance.sync(self.rpr_context, inst, indirect_only=indirect_only,
                          frame_current=scene.frame_current)

        # rpr_context parameters
        self.rpr_context.set_parameter(pyrpr.CONTEXT_PREVIEW, False)
        scene.rpr.export_ray_depth(self.rpr_context)
        self.rpr_context.texture_compression = scene.rpr.texture_compression

        # EXPORT CAMERA
        camera_key = object.key(scene.camera)   # current camera key
        rpr_camera = self.rpr_context.create_camera(camera_key)
        self.rpr_context.scene.set_camera(rpr_camera)
        camera_obj = depsgraph.objects.get(camera_key, None)
        if not camera_obj:
            camera_obj = scene.camera

        camera_data = camera.CameraData.init_from_camera(camera_obj.data, camera_obj.matrix_world,
                                                         self.rpr_context.width / self.rpr_context.height)
        camera_data.export(rpr_camera)

        # sync Motion Blur
        self.rpr_context.do_motion_blur = scene.render.use_motion_blur and \
                                          not math.isclose(scene.camera.data.rpr.motion_blur_exposure, 0.0)

        if self.rpr_context.do_motion_blur:
            self.sync_motion_blur(depsgraph)
            rpr_camera.set_exposure(scene.camera.data.rpr.motion_blur_exposure)
            self.set_motion_blur_mode(scene)

        # adaptive subdivision will be limited to the current scene render size
        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)
        self.rpr_context.sync_auto_adapt_subdivision()

        self.rpr_context.sync_portal_lights()

        # Exported scene will be rendered vertically flipped, flip it back
        self.rpr_context.set_parameter(pyrpr.CONTEXT_Y_FLIP, True)

        log('Finish sync')

    def _set_scene_frame(self, scene, frame, subframe=0.0):
        scene.frame_set(frame, subframe=subframe)

    def export_to_rpr(self, filepath: str, flags):
        """
        Export scene to RPR file
        :param filepath: full output file path, including filename extension
        """
        log('export_to_rpr')
        pyrpr_load_store.export(filepath, self.rpr_context.context, self.rpr_context.scene, flags)


class ExportEngine2(ExportEngine):
    TYPE = 'EXPORT'

    def __init__(self):
        self.rpr_context = RPRContext2()
        self.rpr_context.engine_type = self.TYPE
