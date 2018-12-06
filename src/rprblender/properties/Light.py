import bpy
from bpy.props import (
    PointerProperty,
)

from .base import RPR_Property, RPR_Panel


class RPR_PROPS_PhysicalLightSettings(RPR_Property):

    def sync(self, context):
        ''' sync the mesh '''
        light = self.id_data
        print("Syncing Light %s " % light.name)

class RPR_DATA_PT_light(RPR_Panel):
    """
    Physical light sources
    """
    bl_idname = 'rpr_data_PT_light'
    bl_label = "Light Settings"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.light and RPR_Panel.poll(context)

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        light = context.light

        layout.prop(light, "type", expand=True)


classes = (RPR_PROPS_PhysicalLightSettings, RPR_DATA_PT_light)
