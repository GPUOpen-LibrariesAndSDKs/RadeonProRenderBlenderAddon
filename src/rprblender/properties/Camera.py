import bpy
from bpy.props import (
    PointerProperty,
    FloatProperty,
    BoolProperty,
)

import pyrpr
from rprblender import logging
from . import RPR_Panel, RPR_Properties


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

    def sync(self, context, transform):
        def get_look_at(m):
            pos = m.dot([0, 0, 0, 1])[:3]
            at = m.dot([0, 0, -1, 1])[:3]
            up = m.dot([0, 1, 0, 0])[:3]
            return pos, at, up

        camera = self.id_data
        print("Syncing camera: %s" % camera.name)
        
        rpr_camera = context.create_camera()
        rpr_camera.set_name(camera.name)
        
        pos, at, up = get_look_at(transform)
        rpr_camera.look_at(pos, at, up)

        mode = {
            'ORTHO': pyrpr.CAMERA_MODE_ORTHOGRAPHIC,
            'PERSP': pyrpr.CAMERA_MODE_PERSPECTIVE,
            'PANO': pyrpr.CAMERA_MODE_LATITUDE_LONGITUDE_360,
            }[camera.type]
        rpr_camera.set_mode(mode)

        rpr_camera.set_focal_length(camera.lens)
        rpr_camera.set_sensor_size(camera.sensor_width, camera.sensor_height)

    @classmethod
    def register(cls):
        logging.info("register", tag='Camera')
        bpy.types.Camera.rpr = PointerProperty(
            name="RPR Camera Settings",
            description="RPR Camera settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        logging.info("unregister", tag='Camera')
        del bpy.types.Camera.rpr


class RPR_CAMERA_PT_motion_blur(RPR_Panel):
    bl_idname = 'rpr_data_PT_camera_motion_blur'
    bl_label = "RPR Motion Blur"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.camera and RPR_Panel.poll(context)

    def draw_header(self, context):
        row = self.layout.row()
#        row.active = context.scene.rpr.render.motion_blur
        row.prop(context.camera.rpr, 'motion_blur', text='')

    def draw(self, context):
        self.layout.use_property_split = True
        row = self.layout.row()
#        row.active = context.scene.rpr.render.motion_blur
        row.enabled = context.camera.rpr.motion_blur
        row.prop(context.camera.rpr, 'motion_blur_exposure')


classes_to_register = (RPR_CameraProperties, RPR_CAMERA_PT_motion_blur)
