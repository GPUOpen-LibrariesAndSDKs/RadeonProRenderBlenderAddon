import bpy
from bpy.props import (
    BoolProperty,
    PointerProperty,
)

from rprblender.utils import logging
from . import RPR_Properties


log = logging.Log(tag='Object')


class RPR_ObjectProperites(RPR_Properties):
    """
    Properties for objects
    """

    visibility_in_primary_rays: bpy.props.BoolProperty(
        name="Camera Visibility",
        description="This object will be visible in camera rays",
        default=True,
    )

    reflection_visibility: bpy.props.BoolProperty(
        name="Reflections Visibility",
        description="This object will be visible in reflections",
        default=True,
    )

    shadows: BoolProperty(
        name="Casts Shadows",
        description="This object will cast shadows",
        default=True,
    )

    shadowcatcher: BoolProperty(
        name="Shadow Catcher",
        description="Use this object as a shadowcatcher",
        default=False,
    )

    motion_blur: bpy.props.BoolProperty(
        name="Motion Blur",
        description="Enable Motion Blur",
        default=True,
    )

    motion_blur_scale: bpy.props.FloatProperty(
        name="Scale",
        description="Motion Blur Scale",
        default=1.0,
        min=0,
    )

    def sync(self, rpr_context):
        ''' sync the object and any data attached '''
        obj = self.id_data

        log("Syncing object: {}, type {}".format(obj.name, obj.type))

        if obj.type in ['MESH', 'CAMERA', 'LIGHT']:
            obj.data.rpr.sync(rpr_context, obj)

    @classmethod
    def register(cls):
        log("Register")
        bpy.types.Object.rpr = PointerProperty(
            name="RPR Object Settings",
            description="RPR Object settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Unregister")
        del bpy.types.Object.rpr
