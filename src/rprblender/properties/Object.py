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

    def sync(self, context: engine.context.Context):
        ''' sync the object and any data attached '''
        obj = self.id_data
        log("Syncing object: {}, type {}".format(obj.name, obj.type))

        object = None
        transform = np.array(obj.matrix_world, dtype=np.float32).reshape(4, 4)
        if obj.type in ('MESH',) and self.camera_visible:
            object = obj.data.rpr.sync(context)
            if object:
                has_material = hasattr(obj, 'material_slots')
                if has_material:
                    for name, slot in obj.material_slots.items():
                        log("Syncing material: \"{}\" {}".format(name, slot))
                        material = slot.material.rpr.sync(context)
                        if material:
                            material.attach(object)
                            material.commit()
        elif obj.type in ('CAMERA', 'LIGHT'):
            object = obj.data.rpr.sync(context)
        if object:
            object.set_transform(transform)

    def fake_material(self):
        return None

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
