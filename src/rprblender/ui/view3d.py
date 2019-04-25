import bpy


class RPR_VIEW3D_MT_menu(bpy.types.Menu):
    bl_label = "RPR"
    bl_idname = 'RPR_VIEW3D_MT_menu'

    def draw(self, context):
        layout = self.layout
        layout.prop_menu_enum(context.scene.rpr, 'render_mode')


def draw_menu(self, context):
    """ Draws 'RPR' menu item if RPR engine is active """
    if context.engine == 'RPR':
        self.layout.menu(RPR_VIEW3D_MT_menu.bl_idname)
