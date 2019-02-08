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
from rprblender.utils import image as image_utils
from rprblender.utils import logging
import rprblender.utils.light as light_ut
import rprblender.utils.mesh as mesh_ut
from . import RPR_Properties
from . import SyncError


log = logging.Log(tag='Light')

MAX_LUMINOUS_EFFICACY = 683.0


class RPR_LightProperties(RPR_Properties):
    # LIGHT INTENSITY
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
        name="Units",
        items=intensity_units_items_default + intensity_units_items_point,
        description="Intensity Units",
        default='DEFAULT',
    )
    intensity_units_dir: EnumProperty(
        name="Units",
        items=intensity_units_items_default + intensity_units_items_dir,
        description="Intensity Units",
        default='DEFAULT',
    )
    intensity_units_area: EnumProperty(
        name="Units",
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

    # LIGHT COLOR
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

    # POINT LIGHT
    ies_file_name: StringProperty(
        name='IES File', description='IES data file name',
        default='',
    )

    # SUN LIGHT
    shadow_softness: FloatProperty(
        name="Shadow Softness",
        description="Edge shadow softness. Increase for lighter shadows",
        min=0.0, max=1.0, default=0.0
    )

    # AREA LIGHT
    def update_shape(self, context):
        light = context.object.data
        light.shape = self.shape if self.shape != 'MESH' else 'SQUARE'

    shape: EnumProperty(
        name="Shape",
        items=(
            ('SQUARE', "Square", "Rectangle shape"),
            ('RECTANGLE', "Rectangle", "Rectangle shape"),
            ('DISK', "Disk", "Disk shape"),
            ('ELLIPSE', "Ellipse", "Ellipse shape"),
            ('MESH', "Mesh", "Custom mesh"),   # TODO: Implement drawing of custom mesh
        ),
        description="Shape of the area Light",
        default='RECTANGLE',
        update=update_shape
    )
    color_map: PointerProperty(
        type=bpy.types.Image,
        name="Color Map",
        description="Area light color map",
    )
    mesh: PointerProperty(
        type=bpy.types.Mesh,
        name="Mesh",
        description="Select mesh object",
    )
    visible: BoolProperty(
        name="Visible",
        description="Light object to be visible",
        default=False
    )
    cast_shadows: BoolProperty(
        name = "Cast Shadows",
        description="Enable shadows from other light sources",
        default=False
    )

    # LIGHT GROUP AOV
    group: EnumProperty(
        name="Light Group",
        items=(('KEY', "Key", "Key"),
               ('FILL', "Fill", "Fill")),
        description="Light group for doing split lighting AOVs",
        default='KEY',
    )

    def sync(self, rpr_context, obj):
        ''' sync the light '''

        light = self.id_data
        log("Syncing light: {}".format(light.name))

        area = 0.0

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
            if self.shape == 'MESH':
                if not self.mesh:
                    raise SyncError("Area light %s has no mesh" % light.name, light)

                data = mesh_ut.get_mesh_data(self.mesh, calc_area=True)

            else:
                data = light_ut.get_area_light_mesh_data(self.shape, light.size, light.size_y, segments=32)

            area = data.area

            rpr_light = rpr_context.create_area_light(
                utils.key(obj),
                data.vertices, data.normals, data.uvs,
                data.vertex_indices, data.normal_indices, data.uv_indices,
                data.num_face_vertices
            )

            rpr_light.set_visibility(self.visible)
            rpr_light.set_shadow(self.visible and self.cast_shadows)

            if self.color_map:
                rpr_light.set_image(image_utils.get_rpr_image(rpr_context, self.color_map))

        else:
            raise SyncError("Light %s has unsupported type %s" % (light.name, light.type), light)

        rpr_light.set_name(light.name)

        power = self._get_radiant_power(area)
        rpr_light.set_radiant_power(*power)
        rpr_light.set_transform(utils.get_transform(obj))
        rpr_light.set_group_id(1 if light.rpr.group == 'KEY' else 2)

        rpr_context.scene.attach(rpr_light)

    def sync_update(self, rpr_context, obj, is_updated_geometry, is_updated_transform):
        light = self.id_data
        log("Updating light: {}".format(light.name))

        res = False

        rpr_light = rpr_context.objects.get(utils.key(obj), None)
        if rpr_light:
            if is_updated_geometry:
                # TODO: recreate light
                pass

            if is_updated_transform:
                rpr_light.set_transform(utils.get_transform(obj))
                res = True

        else:
            self.sync(rpr_context, obj)
            res = True

        return res

    def _get_radiant_power(self, area=0):
        light = self.id_data

        # calculating color intensity
        color = np.array(light.color)
        if self.use_temperature:
            color *= light_ut.convert_kelvins_to_rgb(self.temperature)
        intensity = color * self.intensity

        # calculating radian power for core
        if light.type in ('POINT', 'SPOT'):
            units = self.intensity_units_point
            if units == 'DEFAULT':
                return intensity / (4*math.pi)  # dividing by 4*pi to be more convenient with cycles point light

            # converting to lumens
            if units == 'LUMEN':
                lumens = intensity
            else:  # 'WATTS'
                lumens = intensity * self.luminous_efficacy
            return lumens / MAX_LUMINOUS_EFFICACY

        elif light.type == 'SUN':
            units = self.intensity_units_dir
            if units == 'DEFAULT':
                return intensity * 0.01         # multiplying by 0.01 to be more convenient with point light

            # converting to luminance
            if units == 'LUMINANCE':
                luminance = intensity
            if units == 'RADIANCE':
                luminance = intensity * self.luminous_efficacy
            return luminance / MAX_LUMINOUS_EFFICACY

        elif light.type == 'AREA':
            units = self.intensity_units_area
            if units == 'DEFAULT':
                if self.intensity_normalization:
                    return intensity / area
                return intensity

            # converting to luminance
            if units == 'LUMEN':
                luminance = intensity / area
            if units == 'WATTS':
                luminance = intensity * self.luminous_efficacy / area
            if units == 'LUMINANCE':
                luminance = intensity
            if units == 'RADIANCE':
                luminance = intensity * self.luminous_efficacy
            return luminance / MAX_LUMINOUS_EFFICACY

    @classmethod
    def register(cls):
        log("Register")
        bpy.types.Light.rpr = PointerProperty(
            name="RPR Light Settings",
            description="RPR light settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Unregister")
        del bpy.types.Light.rpr
