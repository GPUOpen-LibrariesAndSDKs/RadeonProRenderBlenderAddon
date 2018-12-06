import bpy
from bpy.types import Operator

from .base import RPR_Panel
from rprblender import logging


class RPR_OT_UseShadingNodes(Operator):
    """
    Enable nodes on a material, world or light
    """
    bl_idname = 'rpr.use_shading_nodes'
    bl_label = "Use Nodes"

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return (getattr(context, 'material', False) or getattr(context, 'world', False) or
                getattr(context, 'light', False))

    def execute(self, context: bpy.types.Context):
        logging.info("Enabling nodes for {}".format(context))
        if context.material:
            context.material.use_nodes = True
        elif context.world:
            context.world.use_nodes = True
        elif context.light:
            context.light.use_nodes = True

        return {'FINISHED'}


class RPR_PT_material(RPR_Panel, bpy.types.Panel):
    bl_idname = 'rpr_materail_PT_properties'
    bl_label = "RPR Settings"
    bl_space_type = 'PROPERTIES'
    bl_context = 'material'
    bl_region_type = 'WINDOW'
    COMPAT_ENGINES = {'RPR'}

    @classmethod
    def poll(cls, context):
        return context.material

    def draw(self, context):
        layout = self.layout

        mat = context.material
        layout.operator('rpr.use_shading_nodes', icon='NODETREE')


classes = (RPR_OT_UseShadingNodes, RPR_PT_material)
