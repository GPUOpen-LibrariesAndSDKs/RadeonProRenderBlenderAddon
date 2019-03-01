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
    light,
)

register, unregister = bpy.utils.register_classes_factory([
    render.RPR_RENDER_OP_open_web_page,

    world.RPR_WORLD_OP_create_environment_gizmo,
    world.RPR_WORLD_OT_convert_cycles_environment,

    light.RPR_LIGHT_OP_select_ies_file,
    light.RPR_LIGHT_OP_remove_ies_file,
])
