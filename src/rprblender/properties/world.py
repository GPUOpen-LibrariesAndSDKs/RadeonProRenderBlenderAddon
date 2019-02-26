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
        name='Color',
        description="Color to use when as a constant environment light",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    ibl_intensity: FloatProperty(
        name="Intensity",
        description="Intensity",
        min=0.0, default=1.0,
    )
    ibl_image: PointerProperty(
        type=bpy.types.Image
    )

    # sun and sky

    # overrides

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
