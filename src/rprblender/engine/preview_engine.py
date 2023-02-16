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
import numpy as np
import bpy
import pyrpr

from .engine import Engine
from rprblender.export import object, camera, world
from .context import RPRContext2

from rprblender.utils import logging, BLENDER_VERSION
log = logging.Log(tag='PreviewEngine')



CONTEXT_LIFETIME = 300.0    # 5 minutes in seconds


class PreviewEngine(Engine):
    """ Render engine for preview material, lights, environment """

    TYPE = 'PREVIEW'

    _RPRContext = RPRContext2
    rpr_context = None

    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)

        self.is_synced = False
        self.render_samples = 0
        self.render_update_samples = 1

    def _init_rpr_context(self, scene):
        if not PreviewEngine.rpr_context:
            log("Creating RPRContext")
            PreviewEngine.rpr_context = self._RPRContext()
            scene.rpr.init_rpr_context(PreviewEngine.rpr_context, is_final_engine=False)
            PreviewEngine.rpr_context.scene.set_name(scene.name)

        self.rpr_context = PreviewEngine.rpr_context

    @staticmethod
    def reset():
        if PreviewEngine.rpr_context:
            log("Removing RPRContext")
            # Here we remove only link to rpr_context instance.
            # Real deletion will be applied after all links be lost.
            PreviewEngine.rpr_context = None

    def render(self):
        if not self.is_synced:
            return

        log(f"Start render [{self.rpr_context.width}, {self.rpr_context.height}]")
        result = self.rpr_engine.begin_result(0, 0, self.rpr_context.width, self.rpr_context.height)
        sample = 0

        try:
            while sample < self.render_samples:
                if self.rpr_engine.test_break():
                    break

                update_samples = min(self.render_update_samples, self.render_samples - sample)

                log(f"  samples: {sample} +{update_samples} / {self.render_samples}")
                self.rpr_context.set_parameter(pyrpr.CONTEXT_ITERATIONS, update_samples)
                self.rpr_context.render(restart=(sample == 0))
                self.rpr_context.resolve()

                image = self.rpr_context.get_image().flatten()
                if BLENDER_VERSION >= '3.4':
                    # before version 3.4 result.layers[0].passes == ['Combined']
                    # since version 3.4 result.layers[0].passes == ['Combined', 'Depth']
                    # we need to add Depth AOV to keep correct array size while using foreach_set
                    image = np.concatenate(
                        (image, self.rpr_context.get_image(pyrpr.AOV_DEPTH).flatten())
                    )

                result.layers[0].passes.foreach_set('rect', image)
                self.rpr_engine.update_result(result)

                sample += update_samples
        finally:
            self.rpr_engine.end_result(result)

        # clearing scene after finishing render
        self.rpr_context.clear_scene()

        log('Finish render')

    def sync(self, depsgraph):
        log('Start syncing')
        self.is_synced = False

        scene = depsgraph.scene
        settings_scene = bpy.context.scene

        self._init_rpr_context(scene)
        self.rpr_context.resize(scene.render.resolution_x, scene.render.resolution_y)

        self.rpr_context.blender_data['depsgraph'] = depsgraph

        # export visible objects
        for obj in self.depsgraph_objects(depsgraph):
            object.sync(self.rpr_context, obj)

        # export camera
        preview_camera = next((obj for obj in depsgraph.objects if isinstance(obj.data, bpy.types.Camera)))
        camera.sync(self.rpr_context, preview_camera)

        # export world only if active_material.use_preview_world is enabled
        preview_obj = next((obj for obj in self.depsgraph_objects(depsgraph)
                            if obj.name.startswith('preview_')), None)
        if preview_obj and settings_scene.world and preview_obj.active_material \
                and preview_obj.active_material.use_preview_world:
            world.sync(self.rpr_context, settings_scene.world)

        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)
        self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)

        self.rpr_context.set_parameter(pyrpr.CONTEXT_PREVIEW, True)
        settings_scene.rpr.export_ray_depth(self.rpr_context)
        settings_scene.rpr.export_pixel_filter(self.rpr_context)
        self.rpr_context.texture_compression = settings_scene.rpr.texture_compression

        self.render_samples = settings_scene.rpr.viewport_limits.preview_samples
        self.render_update_samples = settings_scene.rpr.viewport_limits.preview_update_samples

        self.is_synced = True
        log('Finish sync')
