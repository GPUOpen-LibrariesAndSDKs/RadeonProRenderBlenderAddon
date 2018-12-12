import bpy
from rprblender.utils import is_rpr_active


class RPR_NodeTree(bpy.types.ShaderNodeTree):
    """ This operator is only visible when RPR is the selected render engine"""
    bl_idname = 'RPRTreeType'
    bl_label = "RPR Shader Editor"
    bl_icon = 'MATERIAL'

    @classmethod
    def poll(cls, context):
        return is_rpr_active(context)

    @classmethod
    def get_from_context(cls, context):
        obj = context.active_object
        if obj:
            material = obj.active_material
            if material:
                return material.node_tree, material, material

        return None, None, None
