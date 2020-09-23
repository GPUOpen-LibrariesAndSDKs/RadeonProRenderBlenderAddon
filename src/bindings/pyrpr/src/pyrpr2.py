# **********************************************************************
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
# ********************************************************************
import pyrpr

# will be used in other modules to check if RPR 2 is enabled
enabled = False


class Context(pyrpr.Context):
    def __init__(self, flags: [set, int], props: list = None, use_cache=True):
        super().__init__(flags, props, use_cache)
        self.render_update_callback = None

    def set_render_update_callback(self, callback_func):
        if callback_func:
            @pyrpr.ffi.callback("void(float, void *)")
            def render_update_callback(progress, data):
                callback_func(progress)

            pyrpr.ContextSetParameterByKeyPtr(self, pyrpr.CONTEXT_RENDER_UPDATE_CALLBACK_FUNC,
                                              render_update_callback)
            self.render_update_callback = render_update_callback

        else:
            pyrpr.ContextSetParameterByKeyPtr(self, pyrpr.CONTEXT_RENDER_UPDATE_CALLBACK_FUNC,
                                              pyrpr.ffi.NULL)
            self.render_update_callback = None

    def delete(self):
        self.set_render_update_callback(None)
        super().delete()


class SphereLight(pyrpr.Light):
    def __init__(self, context):
        super().__init__(context)
        pyrpr.ContextCreateSphereLight(self.context, self)

        # keep target intensity and radius to adjust actual intensity when they are changed
        self._radius_squared = 1

    def set_radiant_power(self, r, g, b):
        # Adjust intensity by current radius
        pyrpr.SphereLightSetRadiantPower3f(self,
                                           r / self._radius_squared,
                                           g / self._radius_squared,
                                           b / self._radius_squared)

    def set_radius(self, radius):
        radius = max(radius, 0.01)
        self._radius_squared = radius * radius
        pyrpr.SphereLightSetRadius(self, radius)


class DiskLight(pyrpr.Light):
    def __init__(self, context):
        super().__init__(context)
        pyrpr.ContextCreateDiskLight(self.context, self)

        # keep target intensity and radius to adjust actual intensity when they are changed
        self._radius_squared = 1

    def set_radiant_power(self, r, g, b):
        # Adjust intensity by current radius
        pyrpr.DiskLightSetRadiantPower3f(self,
                                   r / self._radius_squared,
                                   g / self._radius_squared,
                                   b / self._radius_squared)

    def set_cone_shape(self, iangle, oangle):
        # Use external angle oangle
        pyrpr.DiskLightSetAngle(self, oangle)

    def set_radius(self, radius):
        radius = max(radius, 0.01)
        self._radius_squared = radius * radius
        pyrpr.DiskLightSetRadius(self, radius)


class PostEffect:
    def __init__(self, context, post_effect_type):
        pass

    def set_parameter(self, name, param):
        pass
