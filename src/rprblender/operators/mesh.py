import bpy

from . import RPR_Operator


class RPR_MESH_OT_set_secondary_uv_map(RPR_Operator):
    bl_idname = 'rpr.set_secondary_uv_map'
    bl_label = "Secondary UV"
    bl_description = "Set secondary UV Map"

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return super().poll(context)

    def execute(self, context: bpy.types.Context):
        mesh = context.object.data
        mesh.rpr.secondary_uv_layer_index = mesh.uv_layers.active_index

        return {'FINISHED'}
