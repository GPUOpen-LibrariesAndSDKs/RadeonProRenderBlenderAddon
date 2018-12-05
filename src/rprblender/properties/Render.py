import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from .base import PropertyBase, PanelBase
from rprblender import logging


class RPR_RenderProperties(PropertyBase):
    pass

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


class RPR_PT_RenderPanel(PanelBase):
    bl_idname = "RPR_PT_render_properties"
    bl_label = "RPR Render Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = 'WINDOW'
    bl_context = 'render'
    COMPAT_ENGINES = {'RPR'}

    def draw(self, context):
        self.layout.row().label(text="Test label of the RENDER tab")


classes = (RPR_PT_RenderPanel,)
