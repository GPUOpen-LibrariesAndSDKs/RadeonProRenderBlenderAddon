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
import pyrpr
import pyhybridpro

from . import context
from rprblender.config import hybridpro_unsupported_log_warn

from rprblender.utils import logging
log = logging.Log(tag='context_hybridpro')


class RPRContext(context.RPRContext):
    """ Manager of pyhybridpro and pyrpr calls """

    _Context = pyhybridpro.Context
    _Scene = pyhybridpro.Scene

    _MaterialNode = pyhybridpro.MaterialNode
    _ImageData = pyhybridpro.ImageData
    _ImageFile = pyhybridpro.ImageFile

    _PointLight = pyhybridpro.PointLight
    _SphereLight = pyhybridpro.PointLight
    _DirectionalLight = pyhybridpro.DirectionalLight
    _SpotLight = pyhybridpro.SpotLight
    _DiskLight = pyhybridpro.SpotLight
    _IESLight = pyhybridpro.IESLight
    _AreaLight = pyhybridpro.AreaLight
    _EnvironmentLight = pyhybridpro.EnvironmentLight

    _Camera = pyhybridpro.Camera
    _Shape = pyhybridpro.Shape
    _Mesh = pyhybridpro.Mesh
    _Instance = pyhybridpro.Instance
    _Curve = pyhybridpro.Curve
    _HeteroVolume = pyhybridpro.HeteroVolume
    _Grid = pyhybridpro.Grid

    _PostEffect = pyhybridpro.PostEffect

    def init(self, context_flags, context_props):
        context_flags -= {pyrpr.CREATION_FLAGS_ENABLE_GL_INTEROP}
        if context_props[0] == pyrpr.CONTEXT_SAMPLER_TYPE:
            context_props = context_props[2:]
        super().init(context_flags, context_props)

        # enable arithmetic operations on HybridPro
        self.set_parameter(pyrpr.CONTEXT_ENABLE_ARITHMETICS, True)

    def resolve(self, aovs=None):
        pass

    def enable_aov(self, aov_type):
        if aov_type == pyrpr.AOV_VARIANCE:
            log("Unsupported RPRContext.enable_aov(AOV_VARIANCE)")
            return

        if self.is_aov_enabled(aov_type):
            return

        fbs = {}
        fbs['aov'] = pyrpr.FrameBuffer(self.context, self.width, self.height)
        fbs['aov'].set_name("%d_aov" % aov_type)
        fbs['res'] = fbs['aov']
        self.context.attach_aov(aov_type, fbs['aov'])

        self.frame_buffers_aovs[aov_type] = fbs

    def create_material_node(self, material_type):
        try:
            return super().create_material_node(material_type)

        except pyrpr.CoreError as e:
            if e.status == pyrpr.ERROR_UNSUPPORTED:
                if hybridpro_unsupported_log_warn:
                    log.warn("Unsupported RPRContext.create_material_node", material_type)

                return pyhybridpro.EmptyMaterialNode(material_type)

            raise

    def create_buffer(self, data, dtype):
        return None

    def sync_catchers(self, use_transparent_background=False):
        pass

    def create_tiled_image(self, key):
        # Tiled images are unsupported by HybridPro
        return None

    def sync_auto_adapt_subdivision(self, width=0, height=0):
        # Subdivision is unsupported by HybridPro
        pass
