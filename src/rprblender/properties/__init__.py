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
""" property classes should be self contained.  They may include:
    PropertyGroup class
        with properties that can be attached to a blender ID type
        methods for syncing these properties
    And panel classes for displaying these properties

    The idea here is to keep all the properties syncing, data, display etc in one place.
    Basically a "model/view" type pattern where we bring them together for ease of maintenance.
    Slightly inspired by vue.js
"""

import bpy


__all__ = ('RPR_Properties', 'register', 'unregister')


class RPR_Properties(bpy.types.PropertyGroup):
    def sync(self, rpr_context):
        """ Sync will update this object in the context.
            And call any sub-objects that need to be synced
            rpr_context object in the binding will be the only place we keep
            lists of items synced. """
        pass


# Register/unregister all required classes of RPR properties in one go
from . import (
    render,
    object,
    light,
    camera,
    world,
    view_layer,
    material_browser,
    addon,
    mesh,
)


register, unregister = bpy.utils.register_classes_factory([
    render.RPR_RenderRayDepth,
    render.RPR_RenderLimits,
    render.RPR_RenderDevices,
    render.RPR_UserSettings,
    render.RPR_RenderProperties,

    addon.RPR_AddonPreferences,

    object.RPR_ObjectProperites,

    light.RPR_LightProperties,

    camera.RPR_CameraProperties,

    world.RPR_EnvironmentIbl,
    world.RPR_EnvironmentSunSky,
    world.RPR_EnvironmentProperties,

    view_layer.RPR_DenoiserProperties,
    view_layer.RPR_ContourProperties,
    view_layer.RPR_ViewLayerProperites,

    material_browser.RPR_MaterialBrowserProperties,

    mesh.RPR_MeshProperites,
])
