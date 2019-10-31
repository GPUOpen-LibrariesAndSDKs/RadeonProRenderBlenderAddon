import bpy


class RPR_Operator(bpy.types.Operator):
    bl_idname = 'rpr.operator'
    bl_label = "RPR Operator"
    COMPAT_ENGINES = {'RPR'}

    @classmethod
    def poll(cls, context):
        return context.engine in cls.COMPAT_ENGINES


# Register/unregister all required classes of RPR properties in one go
from . import (
    render,
    world,
    nodes,
    material_library,
    export_scene,
    light,
)

register_operators, unregister_operators = bpy.utils.register_classes_factory([
    render.RPR_RENDER_OP_open_web_page,

    world.RPR_WORLD_OP_create_fog_object,

    nodes.RPR_MATERIAL_LIBRARY_OP_arrage_nodes,
    nodes.RPR_MATERIAL_OP_principled_to_uber,

    material_library.RPR_MATERIAL_LIBRARY_OP_import_material,

    export_scene.RPR_EXPORT_OP_export_rpr_scene,

    light.RPR_LIGHT_OP_open_IES_file,
])


def add_rpr_export_menu_item(self, context):
    self.layout.operator(export_scene.RPR_EXPORT_OP_export_rpr_scene.bl_idname,
                         text="Radeon ProRender (.rpr)")


def register():
    register_operators()
    bpy.types.TOPBAR_MT_file_export.append(add_rpr_export_menu_item)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(add_rpr_export_menu_item)
    unregister_operators()
