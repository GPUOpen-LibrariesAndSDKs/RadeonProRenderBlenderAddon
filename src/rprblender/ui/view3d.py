import bpy
import pyhybrid

from . import RPR_Panel


class RPR_VIEW3D_MT_menu(bpy.types.Menu):
    bl_label = "RPR"
    bl_idname = 'RPR_VIEW3D_MT_menu'

    def draw(self, context):
        layout = self.layout
        layout.prop_menu_enum(context.scene.rpr, 'render_mode')


class RPR_VIEW3D_PT_panel(RPR_Panel):
    bl_label = "RPR"
    bl_space_type = 'VIEW_3D'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        rpr = context.scene.rpr

        if pyhybrid.enabled:
            layout.prop(rpr, 'render_quality')

        row = layout.row()
        row.enabled = rpr.render_quality == 'FULL'
        row.prop(rpr, 'render_mode')


def draw_menu(self, context):
    """ Draws 'RPR' menu item if RPR engine is active """
    if context.engine == 'RPR':
        layout = self.layout
        layout.popover('RPR_VIEW3D_PT_panel')
