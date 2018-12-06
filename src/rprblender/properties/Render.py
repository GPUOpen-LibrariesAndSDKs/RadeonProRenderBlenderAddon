import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from .base import RPR_Property, RPR_Panel
from rprblender import logging


class RPR_RenderSettings(RPR_Property):
    @classmethod
    def register(cls):
        bpy.types.Scene.rpr = PointerProperty(
            name="RPR Render Settings",
            description="RPR render settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        del bpy.types.Scene.rpr


class RPR_RENDER_PT_devices(RPR_Panel):
    bl_idname = "rpr_render_PT_devices"
    bl_label = "RPR Render Device Settings"
    bl_context = 'render'

    def draw(self, context):
        layout = self.layout

        scene = context.scene

        layout.row().label(text="Test label of the RENDER tab")


classes = (RPR_RENDER_PT_devices,)
