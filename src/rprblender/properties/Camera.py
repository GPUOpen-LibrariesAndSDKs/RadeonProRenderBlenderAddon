import bpy
from bpy.props import (
    PointerProperty,
    FloatProperty,
    BoolProperty,
)

from rprblender import logging
from .base import RPR_Panel, RPR_Property


class RPR_PROPS_CameraMotionBlur(RPR_Property):
    motion_blur: BoolProperty = BoolProperty(
        name="Motion Blur",
        description="Enable Motion Blur",
        default=True
    )

    motion_blur_exposure: FloatProperty = FloatProperty(
        name="Motion Blur Exposure",
        description="Motion Blur Exposure",
        min=0,
        default=1.0,
    )

    @classmethod
    def register(cls):
        logging.info("register", tag='Camera')
        bpy.types.Camera.rpr_camera = PointerProperty(
            name="RPR Camera Settings",
            description="RPR Camera settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        logging.info("unregister", tag='Camera')
        del bpy.types.Camera.rpr_camera


class RPR_DATA_PT_camera_motion_blur(RPR_Panel):
    bl_idname = 'rpr_data_PT_camera_motion_blur'
    bl_label = "Motion Blur"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.camera and RPR_Panel.poll(context)

    def draw_header(self, context):
        row = self.layout.row()
#        row.active = context.scene.rpr.render.motion_blur
        row.prop(context.camera.rpr_camera, 'motion_blur', text='')

    def draw(self, context):
        self.layout.use_property_split = True
        row = self.layout.row()
#        row.active = context.scene.rpr.render.motion_blur
        row.enabled = context.camera.rpr_camera.motion_blur
        row.prop(context.camera.rpr_camera, 'motion_blur_exposure')


classes = (RPR_PROPS_CameraMotionBlur, RPR_DATA_PT_camera_motion_blur)