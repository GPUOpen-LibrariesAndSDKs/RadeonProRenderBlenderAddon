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
from . import viewport_engine
from . import context_hybridpro

import pyrpr

from rprblender.operators.world import FOG_KEY

from rprblender.utils import logging
log = logging.Log(tag='viewport_engine_hybridpro')


class ViewportEngine(viewport_engine.ViewportEngine):
    _RPRContext = context_hybridpro.RPRContext

    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)

        self.render_image = None
        self.is_denoised = False

    def _resolve(self):
        self.render_image = self.rpr_context.get_image()

    def _get_render_image(self):
        return self.render_image

    def depsgraph_objects(self, depsgraph, with_camera=False):
        for obj in super().depsgraph_objects(depsgraph, with_camera):
            if obj.name == FOG_KEY:
                continue

            yield obj

    def sync(self, context, depsgraph):
        super().sync(context, depsgraph)

        self.rpr_context.set_parameter(pyrpr.CONTEXT_MATERIAL_CACHE, True)
        self.rpr_context.set_parameter(pyrpr.CONTEXT_RESTIR_GI, True)
        self.rpr_context.set_parameter(pyrpr.CONTEXT_RESTIR_GI_BIAS_CORRECTION, 3)
        self.rpr_context.set_parameter(pyrpr.CONTEXT_RESERVOIR_SAMPLING, 2)
        self.rpr_context.set_parameter(pyrpr.CONTEXT_RESTIR_SPATIAL_RESAMPLE_ITERATIONS, 3)
        self.rpr_context.set_parameter(pyrpr.CONTEXT_RESTIR_MAX_RESERVOIRS_PER_CELL, 128)

        log("Finish sync")

    def setup_image_filter(self, settings):
        self.is_denoised = settings['enable']
        self.rpr_context.set_parameter(pyrpr.CONTEXT_PT_DENOISER,
                                       pyrpr.DENOISER_SVGF if self.is_denoised else pyrpr.DENOISER_NONE)

    def notify_status(self, info, status):
        # Adding " | Denoised" to status message
        if self.is_denoised and status in ("Render", "Rendering Done") and info != "Starting...":
            upscaled_index = info.rfind(" | Upscaled")
            if upscaled_index >= 0:
                info = info[:upscaled_index] + " | Denoised" + info[upscaled_index:]
            else:
                info += " | Denoised"

        super().notify_status(info, status)
