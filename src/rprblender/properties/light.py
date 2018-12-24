import bpy
from bpy.props import (
    PointerProperty,
    EnumProperty,
    FloatProperty,
    BoolProperty,
    IntProperty,
    StringProperty,
)
import numpy as np
import math

from rprblender import utils
from rprblender.utils import logging
from . import RPR_Properties


log = logging.Log(tag='Light')

MAX_LUMINOUS_EFFICACY = 683.0


def convert_kelvins_to_rgb(colour_temperature: int) -> tuple:
    # range check
    if colour_temperature < 1000:
        colour_temperature = 1000
    elif colour_temperature > 40000:
        colour_temperature = 40000

    tmp_internal = colour_temperature / 100.0
    # red
    if tmp_internal <= 66:
        red = 255
    else:
        tmp_red = 329.698727446 * math.pow(tmp_internal - 60, -0.1332047592)
        if tmp_red < 0:
            red = 0
        elif tmp_red > 255:
            red = 255
        else:
            red = tmp_red

    # green
    if tmp_internal <= 66:
        tmp_green = 99.4708025861 * math.log(tmp_internal) - 161.1195681661
        if tmp_green < 0:
            green = 0
        elif tmp_green > 255:
            green = 255
        else:
            green = tmp_green
    else:
        tmp_green = 288.1221695283 * math.pow(tmp_internal - 60, -0.0755148492)
        if tmp_green < 0:
            green = 0
        elif tmp_green > 255:
            green = 255
        else:
            green = tmp_green

    # blue
    if tmp_internal >= 66:
        blue = 255
    elif tmp_internal <= 19:
        blue = 0
    else:
        tmp_blue = 138.5177312231 * math.log(tmp_internal - 10) - 305.0447927307
        if tmp_blue < 0:
            blue = 0
        elif tmp_blue > 255:
            blue = 255
        else:
            blue = tmp_blue

    return red / 255.0, green / 255.0, blue / 255.0


class RPR_LightProperties(RPR_Properties):
    intensity: FloatProperty(
        name="Intensity",
        description="Light Intensity",
        min=0.0, step=20,
        default=100.0,
    )

    intensity_units_items_default = (('DEFAULT', "Default", "Default intensity units"),)
    intensity_units_items_point = (('WATTS', "Watts", "Light intensity in Watts (W)"),
                                   ('LUMEN', "Lumen", "Light intensity in Lumen (lm)"))
    intensity_units_items_dir = (('RADIANCE', "Radiance", "Light intensity in Watts per square meter (W/m^2)"),
                                 ('LUMINANCE', "Luminance", "Light intensity in Lumen per square meter (lm/m^2)"))
    intensity_units_point: EnumProperty(
        name="Intensity Units",
        items=intensity_units_items_default + intensity_units_items_point,
        description="Intensity Units",
        default='DEFAULT',
    )
    intensity_units_dir: EnumProperty(
        name="Intensity Units",
        items=intensity_units_items_default + intensity_units_items_dir,
        description="Intensity Units",
        default='DEFAULT',
    )
    intensity_units_area: EnumProperty(
        name="Intensity Units",
        items=intensity_units_items_default + intensity_units_items_point + intensity_units_items_dir,
        description="Intensity Units",
        default='DEFAULT',
    )
    intensity_normalization: BoolProperty(
        name="Intensity Normalization",
        description="Prevents the light intensity from changing if the size of the light changes",
        default=True
    )
    luminous_efficacy: FloatProperty(
        name="Luminous Efficacy",
        description="Luminous Efficacy - amount of Lumen emitted per Watt (lm/W)",
        min=0.0, max=MAX_LUMINOUS_EFFICACY, soft_max=100.0,
        default=17.0
    )

    use_temperature: BoolProperty(
        name="Use Temperature",
        description="Use a temperature setting",
        default=False,
    )
    temperature: IntProperty(
        name="Temperature",
        description="Use a blackbody temperature (in Kelvin). This will be tinted by the color",
        min=1000, max=40000, soft_max=10000,
        default=6500,
    )

    ies_file_name: StringProperty(
        name='IES Data file', description='IES Data file name',
        default='',
    )

    shadow_softness: FloatProperty(
        name="Shadow Softness",
        description="Edge shadow softness. Increase for lighter shadows",
        min=0.0, max=1.0, default=0.0
    )

    group: EnumProperty(
        name="Light Group",
        items=(('KEY', "Key", "Key"),
               ('FILL', "Fill", "Fill")),
        description="Light group for doing split lighting AOVs",
        default='KEY',
    )

    # AREA LIGHT PROPERTIES
    def update_size(self, context):
        # on updating sizes we set to zero default lamp sizes to prevent Blender to draw rectangle gizmo in 3d viewport
        lamp = context.object.data
        lamp.size = 0
        lamp.size_y = 0

    shape: EnumProperty(
        name="Shape of the area lamp",
        items=(('RECTANGLE', "Rectangle", "Rectangle shape"),
               ('DISC', "Disc", "Disc shape"),
               ('SPHERE', "Sphere", "Sphere shape"),
               ('CYLINDER', "Cylinder", "Cylinder shape"),
               ('MESH', "Mesh", "Select mesh object")),
        description="Shape of the area lamp",
        default='RECTANGLE',
        update=update_size
    )

    visible: BoolProperty(
        name="Visible",
        description="Light object to be visible",
        default=False
    )

    def sync(self, rpr_context, obj):
        ''' sync the mesh '''
        light = self.id_data
        log("Syncing light: {}".format(light.name))

        if light.type == 'POINT':
            if light.rpr.ies_file_name:
                rpr_light = rpr_context.create_light(utils.key(obj), 'ies')
                rpr_light.set_image_from_file(light.rpr.ies_file_name, 256, 256)
            else:
                rpr_light = rpr_context.create_light(utils.key(obj), 'point')
        elif light.type in ('SUN', 'HEMI'):  # just in case old scenes will have outdated Hemi
            rpr_light = rpr_context.create_light(utils.key(obj), 'directional')
            rpr_light.set_shadow_softness(light.rpr.shadow_softness)
        elif light.type == 'SPOT':
            rpr_light = rpr_context.create_light(utils.key(obj), 'spot')
            oangle = 0.5 * light.spot_size  # half of spot_size
            iangle = oangle * (1.0 - light.spot_blend * light.spot_blend)  # square dependency of spot_blend
            rpr_light.set_cone_shape(iangle, oangle)
        elif light.type == 'AREA':
            rpr_light = rpr_context.create_light(utils.key(obj), 'point')  # placeholder until area lights support added
        else:
            log.critical("Light {} has unsupported type {}, skipping.".format(light.name, light.type))
            return None

        rpr_light.set_name(light.name)
        power = self._get_radiant_power(light)
        log.debug("light {} power {}".format(light, power))
        rpr_light.set_radiant_power(*power)
        rpr_light.set_transform(utils.get_transform(obj))
        rpr_light.set_group_id(1 if light.rpr.group == 'KEY' else 2)
        rpr_context.scene.attach(rpr_light)

    @staticmethod
    def _get_radiant_power(light, area=0):
        rpr_lamp = light.rpr

        # calculating color intensity
        color = np.array(light.color)
        if rpr_lamp.use_temperature:
            color *= convert_kelvins_to_rgb(rpr_lamp.temperature)
        intensity = color * rpr_lamp.intensity

        # calculating radian power for core
        if light.type in ('POINT', 'SPOT'):
            units = rpr_lamp.intensity_units_point
            if units == 'DEFAULT':
                return intensity / (4*math.pi)  # dividing by 4*pi to be more convenient with cycles point light

            # converting to lumens
            if units == 'LUMEN':
                lumens = intensity
            else:  # 'WATTS'
                lumens = intensity * rpr_lamp.luminous_efficacy
            return lumens / MAX_LUMINOUS_EFFICACY

        elif light.type == 'SUN':
            units = rpr_lamp.intensity_units_dir
            if units == 'DEFAULT':
                return intensity * 0.01         # multiplying by 0.01 to be more convenient with point light

            # converting to luminance
            if units == 'LUMINANCE':
                luminance = intensity
            if units == 'RADIANCE':
                luminance = intensity * rpr_lamp.luminous_efficacy
            return luminance / MAX_LUMINOUS_EFFICACY

        else:
            assert light.type == 'AREA'
            return intensity  # placeholder until area lights support added

            units = rpr_lamp.intensity_units_area
            if units == 'DEFAULT':
                if rpr_lamp.intensity_normalization:
                    return intensity / area
                return intensity

            # converting to luminance
            if units == 'LUMEN':
                luminance = intensity / area
            if units == 'WATTS':
                luminance = intensity * rpr_lamp.luminous_efficacy / area
            if units == 'LUMINANCE':
                luminance = intensity
            if units == 'RADIANCE':
                luminance = intensity * rpr_lamp.luminous_efficacy
            return luminance / MAX_LUMINOUS_EFFICACY

    @classmethod
    def register(cls):
        log("register")
        bpy.types.Light.rpr = PointerProperty(
            name="RPR Light Settings",
            description="RPR light settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("unregister")
        del bpy.types.Light.rpr
