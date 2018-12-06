import bpy
from bpy.types import PointerProperty

from .base import RPR_Property, RPR_Panel


class RPR_LampSettings(RPR_Property):
    @classmethod
    def register(cls):
        bpy.types.Object.rpr = PointerProperty(
            name="RPR Object Settings",
            description="RPR Object settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        del bpy.types.Object.rpr


class RPR_OBJECT_PT_object(RPR_Panel, bpy.types.Panel):
    ''' panel to display above properties '''
    bl_idname = "RPR_lamp_PT_properties"
    bl_label = "RPR Settings"
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object and super().poll(context)

    def draw(self, context):
        if context.object:
            rpr = getattr(context.object, 'rpr', None)
            self.layout.row().label(text="Just the test label")
            if rpr:
                self.layout.row().prop(rpr, "camera_visible")


classes = (RPR_LampSettings, RPR_OBJECT_PT_object)
