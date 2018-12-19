import numpy as np

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from rprblender import logging
from . import RPR_Properties, RPR_Panel


def log(*args):
    logging.info(*args, tag='Object')


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


class RPR_OBJECT_PT_object(RPR_Panel):
    bl_idname = 'rpr_object_pt_object'
    bl_label = "RPR Settings"
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and super().poll(context)

    def draw(self, context):
        if context.object:
            rpr = getattr(context.object, 'rpr', None)
            if rpr and context.object.type == 'MESH':
                self.layout.row().prop(rpr, 'visibility_in_primary_rays')
                self.layout.row().prop(rpr, 'reflection_visibility')
                self.layout.row().prop(rpr, 'shadows')
                self.layout.row().prop(rpr, 'shadowcatcher')


class RPR_OBJECT_PT_motion_blur(RPR_Panel):
    bl_idname = 'rpr_object_pt_motion_blur'
    bl_label = "RPR Motion Blur"
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and super().poll(context)

    def draw(self, context):
        self.layout.active = context.object.rpr.motion_blur
        rpr = getattr(context.object, 'rpr', None)
        if rpr and context.object.type == 'MESH':
            self.layout.row().prop(rpr, 'motion_blur_scale')

    def draw_header(self, context):
        self.layout.prop(context.object.rpr, "motion_blur", text="")


classes_to_register = (RPR_ObjectProperites, RPR_OBJECT_PT_object, RPR_OBJECT_PT_motion_blur)
