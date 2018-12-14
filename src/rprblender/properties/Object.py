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

import pyrpr
from rprblender import logging, engine
from . import RPR_Properties, RPR_Panel
from .Material import RPR_MATERIAL_parser


def log(*args):
    logging.info(*args, tag='Object')


class RPR_ObjectProperites(RPR_Properties):
    """
    Properties for objects
    """

    camera_visible: BoolProperty(
        name="Camera Visibility",
        default=True
    )

    shadowcatcher: BoolProperty(
        name="Shadow Catcher",
        description="Use this object as shadowcatcher",
        default=False,
    )

    cast_shadow: BoolProperty(
        name="Cast Shadow",
        default=True
    )

    receive_shadow: BoolProperty(
        name="Receive Shadow",
        default=True
    )

    def sync(self, rpr_context):
        ''' sync the object and any data attached '''

        if not self.camera_visible:
            return

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
    """
    panel to display above properties
    """

    bl_idname = 'rpr_object_PT_object'
    bl_label = "RPR Settings"
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object and super().poll(context)

    def draw(self, context):
        if context.object:
            rpr = getattr(context.object, 'rpr', None)
            self.layout.row().label(text="Just the test label")
            if rpr and context.object.type == 'OBJECT':
                self.layout.row().prop(rpr, 'camera_visible')
                self.layout.row().prop(rpr, 'shadowcatcher')


classes_to_register = (RPR_ObjectProperites, RPR_OBJECT_PT_object)
