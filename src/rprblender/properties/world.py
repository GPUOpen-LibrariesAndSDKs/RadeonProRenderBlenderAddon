import bpy
from bpy.props import (
    BoolProperty,
    FloatVectorProperty,
    FloatProperty,
    StringProperty,
    EnumProperty,
    PointerProperty,
)

from . import RPR_Properties

from rprblender.utils import logging
log = logging.Log(tag='properties.world')


class RPR_EnvironmentProperties(RPR_Properties):
    """ World environment light and overrides settings """

    enabled: BoolProperty(default=True)
    # environment
    light_type: EnumProperty(
        name="IBL Type",
        items=(('IBL', "IBL Map", "Use IBL environment light"),
               ('SUN_SKY', "Sun & Sky", "Use Sun&Sky"),
               ),
        description="Environment light type",
        default='IBL',
    )

    # ibl
    ibl_type: EnumProperty(
        name="IBL Type",
        items=(('COLOR', "Color", "Use solid color for lighting"),
               ('IBL', "IBL Map", "Use IBL Map for lighting"),
               ),
        description="IBL Type",
        default='COLOR',
    )
    ibl_color: FloatVectorProperty(
        name="Color",
        description="Color to use as a constant environment light",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    ibl_intensity: FloatProperty(
        name="Intensity",
        description="Environment intensity",
        min=0.0, default=1.0,
    )
    ibl_image: PointerProperty(
        type=bpy.types.Image
    )

    # sun and sky

    # overrides
    override_background: bpy.props.BoolProperty(
        name="Override Background", description="Override the IBL background",
        default=False,
    )
    override_reflection: bpy.props.BoolProperty(
        name="Override Reflection", description="Override the IBL background for reflection channel",
        default=False,
    )
    override_refraction: bpy.props.BoolProperty(
        name="Override Refraction", description="Override the IBL background for refraction channel",
        default=False,
    )
    override_transparency: bpy.props.BoolProperty(
        name="Override Transparency", description="Override the IBL background for transparency channel",
        default=False,
    )

    background_type: EnumProperty(
        name="Override Type",
        items=(('COLOR', "Color", "Override the background with a color"),
               ('IMAGE', "Image", "Override the background with an image")),
        description="Background override type",
        default='IMAGE',
    )
    reflection_type: EnumProperty(
        name="Override Type",
        items=(("COLOR", "Color", "Override the background for reflections with a color"),
               ("IMAGE", "Image", "Override the background for reflections with an image")),
        description="Reflection override type",
        default='IMAGE',
    )
    refraction_type: EnumProperty(
        name="Override Type",
        items=(("COLOR", "Color", "Override the background for refraction with a color"),
               ("IMAGE", "Image", "Override the background for refraction with an image")),
        description="Refraction override type",
        default='IMAGE',
    )
    transparency_type: EnumProperty(
        name="Override Type",
        items=(("COLOR", "Color", "Override the background for transparency with a color"),
               ("IMAGE", "Image", "Override the background for transparency with an image")),
        description="Refraction override type",
        default='IMAGE',
    )

    background_image: bpy.props.PointerProperty(type=bpy.types.Image)
    reflection_image: bpy.props.PointerProperty(type=bpy.types.Image)
    refraction_image: bpy.props.PointerProperty(type=bpy.types.Image)
    transparency_image: bpy.props.PointerProperty(type=bpy.types.Image)

    background_color: FloatVectorProperty(
        name="Background Color",
        description="The background override color",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    reflection_color: FloatVectorProperty(
        name="Reflection Color",
        description="The reflection override color",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    refraction_color: FloatVectorProperty(
        name="Refraction Color",
        description="The refraction override color",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    transparency_color: FloatVectorProperty(
        name="Transparency Color",
        description="The transparency override color",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )

    # environment transform gizmo
    def update_gizmo_rotation(self, context):
        if self.gizmo in bpy.data.objects:
            obj = bpy.data.objects[self.gizmo]
            obj.rotation_euler = self.gizmo_rotation

    def update_gizmo(self, context):
        if self.gizmo in bpy.data.objects:
            obj = bpy.data.objects[self.gizmo]
            self['gizmo_rotation'] = obj.rotation_euler

    gizmo_rotation: bpy.props.FloatVectorProperty(
        name='Rotation', description='Rotation',
        subtype='EULER', size=3,
        update=update_gizmo_rotation
    )

    gizmo: bpy.props.StringProperty(
        name="Gizmo",
        description="Environment Helper",
        update=update_gizmo
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
