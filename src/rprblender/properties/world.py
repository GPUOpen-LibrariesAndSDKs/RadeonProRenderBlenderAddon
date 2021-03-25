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
import math

import bpy
from bpy.props import (
    BoolProperty,
    FloatVectorProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
    EnumProperty,
    PointerProperty,
)

from . import RPR_Properties

from rprblender.utils import logging
log = logging.Log(tag='properties.world')


class RPR_EnvironmentSunSky(bpy.types.PropertyGroup):

    type: EnumProperty(
        name="Sun & Sky System",
        items=(('ANALYTICAL', "Analytical Sky", "Analytical Sky"),
               ('DATE_TIME_LOCATION', "Date, Time and Location", "Date, Time and Location")),
        description="Sun & Sky System",
        default='ANALYTICAL',
    )

    # Analytical Sky
    azimuth: FloatProperty(
        name="Azimuth",
        description="Azimuth",
        subtype='ANGLE',
        min=0, max=math.radians(360),
        default=0.0,
    )
    altitude: FloatProperty(
        name="Altitude",
        description="Altitude",
        subtype='ANGLE',
        min=math.radians(-90), max=math.radians(90),
        default=math.radians(30),
    )

    # Date, Time & Location
    latitude: FloatProperty(
        name="Latitude",
        description="Latitude",
        subtype='ANGLE',
        min=math.radians(-90), max=math.radians(90),
        default=math.radians(38),
    )
    longitude: FloatProperty(
        name="Longitude",
        description="Longitude",
        subtype='ANGLE',
        min=math.radians(-180), max=math.radians(180),
        default=math.radians(27),
    )

    date_year: IntProperty(
        name="Year",
        description="Year",
        # subtype='TIME',
        min=0, default=2016,
    )
    date_month: IntProperty(
        name="Month",
        description="Month",
        # subtype='TIME',
        min=1, max=12, default=1,
    )
    date_day: IntProperty(
        name="Day",
        description="Day",
        # subtype='TIME',
        min=1, max=31, default=1,
    )
    time_hours: IntProperty(
        name="Hours",
        description="Hours",
        subtype='TIME',
        min=0, max=23, default=12,
    )
    time_minutes: IntProperty(
        name="Minutes",
        description="Minutes",
        subtype='TIME',
        min=0, max=59, default=0,
    )
    time_seconds: IntProperty(
        name="Seconds",
        description="Seconds",
        subtype='TIME',
        min=0, max=59, default=0,
    )
    time_zone: FloatProperty(
        name="Time Zone",
        description="Time Zone",
        subtype='TIME',
        min=-18, max=18, default=0,
    )
    daylight_savings: BoolProperty(
        name="Daylight Savings Time",
        description="Daylight Savings Time",
        default=True
    )

    # generic Sun & Sky parameters
    turbidity: FloatProperty(
        name="Turbidity",
        description="Turbidity",
        default=0.2,
    )
    sun_glow: FloatProperty(
        name="Sun Glow",
        description="Sun Glow",
        default=1.0,
    )
    sun_disc: FloatProperty(
        name="Sun Disc",
        description="Sun Disc",
        default=2.0,
    )
    saturation: FloatProperty(
        name="Saturation",
        description="Saturation",
        min=0.0, max=1.0,
        default=0.5,
    )
    horizon_height: FloatProperty(
        name="Horizon Height",
        description="Horizon Height",
        default=0.001,
    )
    horizon_blur: FloatProperty(
        name="Horizon Blur",
        description="Horizon Blur",
        default=0.1,
    )

    filter_color: FloatVectorProperty(
        name='Filter Color', description="Filter Color",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.0, 0.0, 0.0)
    )
    ground_color: FloatVectorProperty(
        name='Ground Color', description="Ground Color",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.4, 0.4, 0.4)
    )

    resolution: EnumProperty(
        name="Texture resolution",
        items=(('256', "Small", "Small (256x256) - best performance"),
               ('1024', "Normal", "Normal (1024x1024) - balance between performance and quality"),
               ('4096', "High", "High (4096x4096) - best quality")),
        description="Texture resolution",
        default='1024',
    )


class RPR_EnvironmentIbl(bpy.types.PropertyGroup):
    color: FloatVectorProperty(
        name="Color",
        description="Color to use as a constant environment light",
        subtype='COLOR',
        min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    image: PointerProperty(
        type=bpy.types.Image,
        name="Image"
    )


class RPR_EnvironmentProperties(RPR_Properties):
    """ World environment light and overrides settings """

    enabled: BoolProperty(
        name="Enable Environment",
        description="Enable Environment Light",
        default=True
    )
    mode: EnumProperty(
        name="Environment Type",
        items=(('IBL', "IBL", "Use IBL environment light"),
               ('SUN_SKY', "Sun & Sky", "Use Sun & Sky")),
        description="Environment light type",
        default='IBL',
    )
    intensity: FloatProperty(
        name="Intensity",
        description="Environment intensity",
        min=0.0,
        default=1.0,
    )

    ibl: PointerProperty(type=RPR_EnvironmentIbl)
    sun_sky: PointerProperty(type=RPR_EnvironmentSunSky)

    # background override
    background_override: bpy.props.BoolProperty(
        name="Override Background",
        description="Override the IBL background",
        default=False,
    )
    background_color: FloatVectorProperty(
        name="Color",
        description="Background override color",
        subtype='COLOR',
        min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    background_image: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="Image",
    )
    background_image_type: EnumProperty(
        name="Background Override Type",
        items=(('SPHERE', "Sphere", "360 degrees spherical background image"),
               ('BACKPLATE', "Backplate", "Flat backplate image")),
        description="Background override type",
        default='SPHERE',
    )
    backplate_crop: bpy.props.BoolProperty(
        name="Crop",
        description="Crop backplate image to render size",
        default=True,
    )
    background_rotation_override: bpy.props.BoolProperty(
        name="Override Rotation for Background",
        description="Use separate rotation for background override",
        default=False,
    )
    background_rotation: bpy.props.FloatVectorProperty(
        name="Background Rotation",
        description="Background Rotation Euler Angles",
        subtype='EULER',
        size=3,
    )

    # reflection override
    reflection_override: bpy.props.BoolProperty(
        name="Override Reflection",
        description="Override the IBL background for reflection channel",
        default=False,
    )
    reflection_color: FloatVectorProperty(
        name="Color",
        description="Reflection override color",
        subtype='COLOR',
        min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    reflection_image: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="Image",
    )
    reflection_rotation_override: bpy.props.BoolProperty(
        name="Override Rotation for Reflection",
        description="Use separate rotation for reflection override",
        default=False,
    )
    reflection_rotation: bpy.props.FloatVectorProperty(
        name="Reflection Rotation",
        description="Reflection Rotation Euler Angles",
        subtype='EULER',
        size=3,
    )

    # refraction override
    refraction_override: bpy.props.BoolProperty(
        name="Override Refraction",
        description="Override the IBL background for refraction channel",
        default=False,
    )
    refraction_color: FloatVectorProperty(
        name="Color",
        description="Refraction override color",
        subtype='COLOR',
        min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    refraction_image: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="Image",
    )
    refraction_rotation_override: bpy.props.BoolProperty(
        name="Override Rotation for Refraction",
        description="Use separate rotation for refraction override",
        default=False,
    )
    refraction_rotation: bpy.props.FloatVectorProperty(
        name="Refraction Rotation",
        description="Refraction Rotation Euler Angles",
        subtype='EULER',
        size=3,
    )

    # transparency override
    transparency_override: bpy.props.BoolProperty(
        name="Override Transparency",
        description="Override the IBL background for transparency channel",
        default=False,
    )
    transparency_color: FloatVectorProperty(
        name="Color",
        description="Transparency override color",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    transparency_image: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="Image",
    )
    transparency_rotation_override: bpy.props.BoolProperty(
        name="Override Rotation for Transparency",
        description="Use separate rotation for transparency override",
        default=False,
    )
    transparency_rotation: bpy.props.FloatVectorProperty(
        name="Transparency Rotation",
        description="Transparency Rotation Euler Angles",
        subtype='EULER',
        size=3,
    )

    world_rotation: bpy.props.FloatVectorProperty(
        name="Rotation",
        description="World Rotation Euler Angles",
        subtype='EULER',
        size=3,
    )

    # LIGHT GROUP AOV
    group: EnumProperty(
        name="Light Group",
        items=(('0', "1", "Group 1"),
               ('1', "2", "Group 2"),
               ('2', "3", "Group 3"),
               ('3', "4", "Group 4"),),
        description="Light group for doing split lighting AOVs",
        default='0',
    )

    @classmethod
    def register(cls):
        log("Register")
        bpy.types.World.rpr = bpy.props.PointerProperty(
            name="RPR World Settings",
            description="RPR Environment Settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Unregister")
        del bpy.types.World.rpr
