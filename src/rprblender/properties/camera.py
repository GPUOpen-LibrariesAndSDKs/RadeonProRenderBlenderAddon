import bpy
from bpy.props import (
    PointerProperty,
    FloatProperty,
    BoolProperty,
)

from rprblender import utils
from rprblender.utils import logging
from . import RPR_Properties
import rprblender.utils.camera as camera_ut


log = logging.Log(tag='Camera')


class RPR_CameraProperties(RPR_Properties):
    motion_blur: BoolProperty(
        name="Motion Blur",
        description="Enable Motion Blur",
        default=True
    )

    motion_blur_exposure: FloatProperty(
        name="Motion Blur Exposure",
        description="Motion Blur Exposure",
        min=0,
        default=1.0,
    )

    def sync(self, rpr_context, obj):
        camera = self.id_data
        log("Syncing camera: %s" % camera.name)
        
        rpr_camera = rpr_context.create_camera(utils.key(obj))
        rpr_camera.set_name(camera.name)
        settings = camera_ut.get_camera_data(camera, utils.get_transform(obj), rpr_context.width / rpr_context.height)
        camera_ut.set_camera_data(rpr_camera, settings)

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
