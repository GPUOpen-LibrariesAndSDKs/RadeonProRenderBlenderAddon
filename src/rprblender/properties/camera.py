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
