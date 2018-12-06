import bpy
from bpy.types import Operator

from .base import RPR_Panel
from rprblender import logging


class RPR_MATERIAL_OT_UseShadingNodes(Operator):
    """
    Enable nodes on a material, world or light
    """
    bl_idname = 'rpr.use_material_shading_nodes'
    bl_label = "Use Nodes"

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return hasattr(context, 'material')

    def execute(self, context: bpy.types.Context):
        logging.info("Enabling nodes for {}".format(context))
        if context.material:
            context.material.use_nodes = True

        return {'FINISHED'}


class RPR_MATERIAL_PT_material(RPR_Panel):
    bl_idname = 'rpr_material_PT_properties'
    bl_label = "RPR Settings"
    bl_context = 'material'

    @classmethod
    def poll(cls, context):
        return context.material

    def draw(self, context):
        layout = self.layout

        mat = context.material
        layout.operator('rpr.use_material_shading_nodes', icon='NODETREE')


classes = (RPR_MATERIAL_OT_UseShadingNodes, RPR_MATERIAL_PT_material)
