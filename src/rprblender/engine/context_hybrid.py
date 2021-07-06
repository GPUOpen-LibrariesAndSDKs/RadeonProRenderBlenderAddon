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
import pyhybrid

from . import context
from rprblender.config import hybrid_unsupported_log_warn

from rprblender.utils import logging
log = logging.Log(tag='context_hybrid')


class RPRContext(context.RPRContext):
    """ Manager of pyhybrid and pyrpr calls """

    _Context = pyhybrid.Context
    _Scene = pyhybrid.Scene

    _MaterialNode = pyhybrid.MaterialNode
    _ImageData = pyhybrid.ImageData
    _ImageFile = pyhybrid.ImageFile

    _PointLight = pyhybrid.PointLight
    _SphereLight = pyhybrid.PointLight
    _DirectionalLight = pyhybrid.DirectionalLight
    _SpotLight = pyhybrid.SpotLight
    _DiskLight = pyhybrid.SpotLight
    _IESLight = pyhybrid.IESLight
    _AreaLight = pyhybrid.AreaLight
    _EnvironmentLight = pyhybrid.EnvironmentLight

    _Camera = pyhybrid.Camera
    _Shape = pyhybrid.Shape
    _Mesh = pyhybrid.Mesh
    _Instance = pyhybrid.Instance
    _Curve = pyhybrid.Curve
    _HeteroVolume = pyhybrid.HeteroVolume
    _Grid = pyhybrid.Grid

    _PostEffect = pyhybrid.PostEffect

    def init(self, context_flags, context_props):
        context_flags -= {pyrpr.CREATION_FLAGS_ENABLE_GL_INTEROP}
        if context_props[0] == pyrpr.CONTEXT_SAMPLER_TYPE:
            context_props = context_props[2:]
        super().init(context_flags, context_props)

        # enable arithmetic operations on Hybrid
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
                if hybrid_unsupported_log_warn:
                    log.warn("Unsupported RPRContext.create_material_node", material_type)

                return pyhybrid.EmptyMaterialNode(material_type)

            raise

    def create_buffer(self, data, dtype):
        return None

    def sync_catchers(self, use_transparent_background=False):
        pass

    def create_tiled_image(self, key):
        # Tiled images are unsupported by Hybrid
        return None
