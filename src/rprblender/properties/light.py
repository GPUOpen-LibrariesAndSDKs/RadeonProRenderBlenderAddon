import bpy
from bpy.props import (
    PointerProperty,
    EnumProperty,
    FloatProperty,
    BoolProperty,
    IntProperty,
    StringProperty,
)
from . import RPR_Properties

from rprblender.utils import logging
log = logging.Log(tag='properties.light')


MAX_LUMINOUS_EFFICACY = 683.0   # luminous efficacy of ideal monochromatic 555 nm source


class RPR_LightProperties(RPR_Properties):
    """ Light properties """

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
    ies_file: PointerProperty(
        type=bpy.types.Image,
        description='IES data file',
        name="IES data file"
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
        light.shape = self.shape

    shape: EnumProperty(
        name="Shape",
        items=(
            ('SQUARE', "Square", "Rectangle shape"),
            ('RECTANGLE', "Rectangle", "Rectangle shape"),
            ('DISK', "Disk", "Disk shape"),
            ('ELLIPSE', "Ellipse", "Ellipse shape"),
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
