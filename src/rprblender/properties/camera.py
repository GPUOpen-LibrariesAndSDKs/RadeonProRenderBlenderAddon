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
    PointerProperty,
    FloatProperty,
    BoolProperty,
)

from . import RPR_Properties

from rprblender.utils import logging
log = logging.Log(tag='properties.camera')


class RPR_CameraProperties(RPR_Properties):
    """ Camera properties """

    motion_blur_exposure: FloatProperty(
        name="Exposure",
        description="Camera motion blur exposure",
        min=0.0, soft_max = 1.0,
        default=1.0,
    )

    @classmethod
    def register(cls):
        log("Register")
        bpy.types.Camera.rpr = PointerProperty(
            name="RPR Camera Settings",
            description="RPR Camera settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Unregister")
        del bpy.types.Camera.rpr
