import bpy
from bpy.types import PointerProperty

from .base import RPR_Property, RPR_Panel


class RPR_LightSettings(RPR_Property):
    pass


class RPR_OBJECT_PT_light(RPR_Panel):
    """
    Physical light sources
    """
    bl_idname = "rpr_object_PT_light"
    bl_label = "RPR Lamp Settings"
    bl_context = 'light'

    @classmethod
    def poll(cls, context):
        return context.object and super().poll(context)

    def draw(self, context):
        layout = context.layout

        scene = context.scene
        light = context.light

        layout.prop(light, "type", expand=True)


classes = (RPR_LightSettings, RPR_OBJECT_PT_light)
