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
import bpy
from bpy.props import (
    BoolProperty,
    PointerProperty,
    BoolVectorProperty,
    EnumProperty,
    IntProperty,
    FloatProperty,
)

import pyrpr

from rprblender.utils import logging
from . import RPR_Properties


log = logging.Log(tag='properties.view_layer')


class RPR_DenoiserProperties(RPR_Properties):
    """ Denoiser properties. This is a child property in RPR_ViewLayerProperties """
    enable: BoolProperty(
        description="Enable RPR Denoiser",
        default=False,
    )

    # only enable ML denoiser on windows
    items = (
        ('BILATERAL', "Bilateral", "Bilateral", 0),
        ('LWR', "Local Weighted Regression", "Local Weighted Regression", 1),
        ('EAW', "Edge Avoiding Wavelets", "Edge Avoiding Wavelets", 2),
        ('ML', "Machine Learning", "Machine Learning", 3)
    )

    filter_type: EnumProperty(
        name="Filter Type",
        items=items,
        description="Filter type",
        default='ML'
    )

    scale_by_iterations: BoolProperty(
        name="Scale Denoising Iterations",
        description="Scale the amount of denoiser blur by number of iterations. "
                    "This will give more blur for renders with less samples, "
                    "and become sharper as more samples are added",
        default=True
    )

    # bilateral props
    radius: IntProperty(
        name="Radius",
        description="Radius",
        min = 1, max = 50, default = 1
    )
    p_sigma: FloatProperty(
        name="Position Sigma",
        description="Threshold for detecting position differences",
        min = 0.0, soft_max = 1.0, default = .1
    )

    # EAW props
    color_sigma: FloatProperty(
        name="Color Sigma",
        description="Threshold for detecting color differences",
        min = 0.0, soft_max = 1.0, default = .75
    )
    normal_sigma: FloatProperty(
        name="Normal Sigma",
        description="Threshold for detecting normal differences",
        min = 0.0, soft_max = 1.0, default = .01
    )
    depth_sigma: FloatProperty(
        name="Depth Sigma",
        description="Threshold for detecting z depth differences",
        min = 0.0, soft_max = 1.0, default = .01
    )
    trans_sigma: FloatProperty(
        name="ID Sigma",
        description="Threshold for detecting Object ID differences",
        min = 0.0, soft_max = 1.0, default = .01
    )

    # LWR props
    samples: IntProperty(
        name="Samples",
        description="Number of samples used, more will give better results while being longer",
        min = 2, soft_max = 10, max = 100, default = 4
    )
    half_window: IntProperty(
        name="Filter radius",
        description="The radius of pixels to sample from",
        min = 1, soft_max = 10, max = 100, default = 4
    )
    bandwidth: FloatProperty(
        name="Bandwidth",
        description="Bandwidth of the filter, a samller value gives less noise, but may filter image detail",
        min = 0.1, max = 1.0, default = .2
    )

    # ML props
    ml_color_only: BoolProperty(
        name="Use Color AOV only",
        description="Use Color AOV only instead of using additional required AOVs",
        default=False
    )
    ml_use_fp16_compute_type: BoolProperty(
        name="Use 16-bit Compute",
        description="Reduce precision to 16 bit. It uses less memory generally for similar quality.\n"
                    "Available only for viewport render",
        default=True
    )
    def get_settings(self, scene, is_final_engine=True):
        return {
            'enable': self.enable and self.is_available(scene, is_final_engine),
            'filter_type': self.filter_type,
            'color_sigma': self.color_sigma,
            'normal_sigma': self.normal_sigma,
            'p_sigma': self.p_sigma,
            'depth_sigma': self.depth_sigma,
            'trans_sigma': self.trans_sigma,
            'radius': self.radius,
            'samples': self.samples,
            'half_window': self.half_window,
            'bandwidth': self.bandwidth,
            'ml_color_only': self.ml_color_only,
            'ml_use_fp16_compute_type': self.ml_use_fp16_compute_type,
        }

    def is_available(self, scene, is_final_engine=True):
        return True


class RPR_ViewLayerProperites(RPR_Properties):
    """
    Properties for view layer with AOVs
    """

    aovs_info = (
        {
            'rpr': pyrpr.AOV_COLOR,
            'name': "Combined",
            'channel': 'RGBA'
        },
        {
            'rpr': pyrpr.AOV_DEPTH,
            'name': "Depth",
            'channel': 'Z'
        },
        {
            'rpr': pyrpr.AOV_COLOR,
            'name': "Color",
            'channel': 'RGBA'
        },
        {
            'rpr': pyrpr.AOV_UV,
            'name': "UV",
            'channel': 'UVA'
        },
        {
            'rpr': pyrpr.AOV_OBJECT_ID,
            'name': "Object Index",
            'channel': 'X'
        },
        {
            'rpr': pyrpr.AOV_MATERIAL_ID,
            'name': "Material Index",
            'channel': 'X'
        },
        {
            'rpr': pyrpr.AOV_WORLD_COORDINATE,
            'name': "World Coordinate",
            'channel': 'XYZ'
        },
        {
            'rpr': pyrpr.AOV_GEOMETRIC_NORMAL,
            'name': "Geometric Normal",
            'channel': 'XYZ'
        },
        {
            'rpr': pyrpr.AOV_SHADING_NORMAL,
            'name': "Shading Normal",
            'channel': 'XYZ'
        },
        {
            'rpr': pyrpr.AOV_OBJECT_GROUP_ID,
            'name': "Group Index",
            'channel': 'X'
        },
        {
            'rpr': pyrpr.AOV_SHADOW_CATCHER,
            'name': "Shadow Catcher",
            'channel': 'A'
        },
        {
            'rpr': pyrpr.AOV_REFLECTION_CATCHER,
            'name': "Reflection Catcher",
            'channel': 'A'
        },
        {
            'rpr': pyrpr.AOV_BACKGROUND,
            'name': "Background",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_EMISSION,
            'name': "Emission",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_VELOCITY,
            'name': "Velocity",
            'channel': 'XYZ'
        },
        {
            'rpr': pyrpr.AOV_DIRECT_ILLUMINATION,
            'name': "Direct Illumination",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_INDIRECT_ILLUMINATION,
            'name': "Indirect Illumination",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_AO,
            'name': "Ambient Occlusion",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_DIRECT_DIFFUSE,
            'name': "Direct Diffuse",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_DIRECT_REFLECT,
            'name': "Direct Reflect",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_INDIRECT_DIFFUSE,
            'name': "Indirect Diffuse",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_INDIRECT_REFLECT,
            'name': "Indirect Reflect",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_REFRACT,
            'name': "Refraction",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_VOLUME,
            'name': "Volume",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_OPACITY,
            'name': "Opacity",
            'channel': 'A'
        },
        {
            'rpr': pyrpr.AOV_LIGHT_GROUP0,
            'name': "Light Group 1",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_LIGHT_GROUP1,
            'name': "Light Group 2",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_LIGHT_GROUP2,
            'name': "Light Group 3",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_LIGHT_GROUP3,
            'name': "Light Group 4",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_VARIANCE,
            'name': "Color Variance",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_DIFFUSE_ALBEDO,
            'name': "Diffuse Albedo",
            'channel': 'RGB'
        },
    )

    # we went over 32 aovs so these must be separated
    cryptomatte_aovs_info = (
        {
            'rpr': pyrpr.AOV_CRYPTOMATTE_MAT0,
            'name': "Cryptomatte Mat0",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_CRYPTOMATTE_MAT1,
            'name': "Cryptomatte Mat1",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_CRYPTOMATTE_MAT2,
            'name': "Cryptomatte Mat2",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_CRYPTOMATTE_OBJ0,
            'name': "Cryptomatte Obj0",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_CRYPTOMATTE_OBJ1,
            'name': "Cryptomatte Obj1",
            'channel': 'RGB'
        },
        {
            'rpr': pyrpr.AOV_CRYPTOMATTE_OBJ2,
            'name': "Cryptomatte Obj2",
            'channel': 'RGB'
        },
    )

    def aov_enabled_changed(self, context):
        """ Request update of active render passes for Render Layers compositor input node """
        context.view_layer.update_render_passes()

    enable_aovs: BoolVectorProperty(
        name="Render Passes (AOVs)",
        description="Render passes (Arbitrary output variables)",
        size=len(aovs_info),
        default=tuple(aov['name'] in ["Combined", "Depth"] for aov in aovs_info),
        update=aov_enabled_changed,
    )

    crytomatte_aov_object: BoolProperty(
        name="Cryptomatte Object AOVs",
        description="Enable Object Cryptomatte AOVs",
        default=False,
        update=aov_enabled_changed,
    )

    crytomatte_aov_material: BoolProperty(
        name="Cryptomatte Material AOVs",
        description="Enable Material Cryptomatte AOVs",
        default=False,
        update=aov_enabled_changed,
    )
    # TODO: Probably better to create each aov separately like: aov_depth: BoolProperty(...)

    denoiser: PointerProperty(type=RPR_DenoiserProperties)

    def get_enabled_aovs(self, cryptomatte_allowed=True):
        enabled_aovs = []
        
        for i, enable_aov in enumerate(self.enable_aovs):
            if enable_aov:
                enabled_aovs.append(self.aovs_info[i])

        if cryptomatte_allowed:
            if self.crytomatte_aov_material:
                for i in range(3):
                    enabled_aovs.append(self.cryptomatte_aovs_info[i])

            if self.crytomatte_aov_object:
                for i in range(3, 6):
                    enabled_aovs.append(self.cryptomatte_aovs_info[i])
        return enabled_aovs

    def export_aovs(self, view_layer: bpy.types.ViewLayer, rpr_context, rpr_engine, enable_adaptive, cryptomatte_allowed):
        """
        Exports AOVs settings. Also adds required passes to rpr_engine
        Note: view_layer here is parent of self, but it is not available from self.id_data
        """

        log(f"Syncing view layer: {view_layer.name}")

        # should always be enabled
        rpr_context.enable_aov(pyrpr.AOV_COLOR)
        rpr_context.enable_aov(pyrpr.AOV_DEPTH)

        for aov in self.get_enabled_aovs(cryptomatte_allowed=cryptomatte_allowed):
            if aov['rpr'] == pyrpr.AOV_VARIANCE and not enable_adaptive:
                continue

            if aov['name'] not in ["Combined", "Depth"]:
                # TODO this seems to assume that combine and depth enabled already?
                rpr_engine.add_pass(aov['name'], len(aov['channel']), aov['channel'], layer=view_layer.name)

            rpr_context.enable_aov(aov['rpr'])

    def enable_aov_by_name(self, name):
        ''' Enables a give aov name '''
        for i, aov_info in enumerate(self.aovs_info):
            if aov_info['name'] == name:
                self.enable_aovs[i] = True
                return

    @classmethod
    def register(cls):
        log("Register")
        bpy.types.ViewLayer.rpr = PointerProperty(
            name="RPR ViewLayer Settings",
            description="RPR view layer settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Unregister")
        del bpy.types.ViewLayer.rpr
