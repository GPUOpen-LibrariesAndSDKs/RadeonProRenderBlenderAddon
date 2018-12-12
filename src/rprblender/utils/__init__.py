import bpy


def is_rpr_active(context: bpy.types.Context):
    return context.scene.render.engine == 'RPR'
