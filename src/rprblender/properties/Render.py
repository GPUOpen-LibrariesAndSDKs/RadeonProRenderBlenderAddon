import bpy

from . import base
from rprblender.utils import logging


class RPR_RenderProperties(base.PropertyBase):
    pass


class RPR_PT_RenderPanel(base.PanelBase):
    bl_idname = "RPR_PT_render_properties"
    bl_label = "RPR Render Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = 'WINDOW'
    bl_context = 'render'
    COMPAT_ENGINES = {'RPR'}

    def draw(self, context):
        self.layout.row().label(text="Test label of the RENDER tab")


classes = (RPR_PT_RenderPanel,)
