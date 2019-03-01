import bpy
import pyrpr

from rprblender.engine.context import RPRContext
from rprblender.nodes.node_parser import NodeParser
from . import key

from rprblender.utils import logging
log = logging.Log(tag='export.Material')


class ShaderNodeOutputMaterial(NodeParser):
    def export(self, input_socket_key='Surface'):
        rpr_node = self.get_input_link(input_socket_key)
        if not rpr_node:
            if input_socket_key == 'Surface':
                # creating error shader
                rpr_node = self.rpr_context.create_material_node(self.node_key, pyrpr.MATERIAL_NODE_PASSTHROUGH)
                rpr_node.set_input('color', (0.0, 0.0, 0.0, 1.0))   # set it to black to correspond to cycles behavior

        return rpr_node


def get_material_output_node(material):
    """ Finds output node in material tree and exports it """

    return next((node for node in material.node_tree.nodes
                      if node.bl_idname == 'ShaderNodeOutputMaterial' and node.is_active_output), None)


def sync(rpr_context: RPRContext, material: bpy.types.Material):
    """
    If material exists: returns existing material
    In other cases: returns None
    """

    log("sync", material)

    mat_key = key(material)

    rpr_material = rpr_context.materials.get(mat_key, None)
    if rpr_material:
        return rpr_material

    output_node = get_material_output_node(material)
    if not output_node:
        log("No output node", material)
        return None

    node_parser = ShaderNodeOutputMaterial(rpr_context, material, output_node, None)
    rpr_material = node_parser.export()

    if rpr_material:
        rpr_context.set_material_node_as_material(mat_key, rpr_material)

    return rpr_material


def sync_update(rpr_context: RPRContext, material: bpy.types.Material):
    """ Recreates existing material """

    log("sync_update", material)

    mat_key = key(material)
    if mat_key in rpr_context.materials:
        rpr_context.remove_material(mat_key)

    sync(rpr_context, material)
    return True
