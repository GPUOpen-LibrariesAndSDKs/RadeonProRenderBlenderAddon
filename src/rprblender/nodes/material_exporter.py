import bpy
import pyrpr
import pyrprx

from .node_parser import NodeParser, get_node_socket, get_rpr_val
from . import MaterialError
from .blender_nodes import blender_node_parsers
from .rpr_nodes import RPRShadingNode
from rprblender import utils
from rprblender.utils.material import find_output_node_in_tree

from rprblender.utils import logging
log = logging.Log(tag='material', level='debug')


ERROR_COLOR = (1.0, 0.0, 1.0, 1.0)

# SUPPORT METHODS

def get_fake_material(rpr_context) -> pyrpr.MaterialNode:
    key = 'FAKE_MATERIAL'

    rpr_mat = rpr_context.materials.get(key, None)
    if rpr_mat:
        return rpr_mat

    rpr_mat = rpr_context.create_material_node('FAKE_MATERIAL_NODE', pyrpr.MATERIAL_NODE_PASSTHROUGH)
    rpr_mat.set_input('color', ERROR_COLOR)
    rpr_context.set_material_node_as_material(key, rpr_mat)

    return rpr_mat


class MaterialExporter:
    ''' Class that handles the exporting and syncing of a material nodetree 
        This will create rpr_node creation objects '''


    def __init__(self, rpr_context, material: bpy.types.Material):
        self.rpr_context = rpr_context
        self.material = material


    def export(self):
        """Entry method to export material if shader nodes tree present.
            Finds the output node and parses node recursively """
        mat_key = utils.key(self.material)

        rpr_material = self.rpr_context.materials.get(mat_key, None)
        if rpr_material:
            return rpr_material

        tree = getattr(self.material, 'node_tree', None)
        if not tree:
            log.warn("Empty material tree, skipping", self.material)
            return None

        log("export", self.material, tree)
        try:
            # looking for output node
            output_node = find_output_node_in_tree(tree)
            if not output_node:
                raise MaterialError("No valid output node found", self.material)

            rpr_material = self.parse_output_node(output_node)
            if rpr_material:
                self.rpr_context.set_material_node_as_material(mat_key, rpr_material)

            return rpr_material

        except MaterialError as e:
            log.error(e, "Fake material would be created")
            return get_fake_material(self.rpr_context)


    def get_node_key(self, node, sub_name=None):
        ''' Get a key (to ref an rpr node) for a given blender node / subnode name.
            we include the subnode name because there might be multiple rpr nodes for 
            a blender node '''
        if sub_name:
            return (utils.key(self.material), node.name, sub_name)

        return (utils.key(self.material), node.name)

    
    def parse_output_node(self, node):
        ''' parse the output node and look for nodes to create recursively ''' 
        surface_socket = get_node_socket(node, name='Surface')  # 'Surface'
        if not surface_socket:
            raise MaterialError("No input for Surface socket", self.material, node)

        log("parse_output_node", self.material, node, surface_socket, surface_socket.node)

        return self.parse_node(surface_socket.node, surface_socket)


    def get_rpr_node_from_key(self, blender_node, socket):
        ''' Gets the rpr node for a give node and output socket if exists, else None '''
        node = self.rpr_context.material_nodes.get(self.get_node_key(blender_node, socket.name), None)
        return node


    def parse_node(self, node, socket):
        ''' parse a blender node by creating node parser objects '''
        log("parse_node", self.material, node, socket)
        
        # check if node is existing
        rpr_node = self.get_rpr_node_from_key(node, socket)
        if rpr_node:
            return rpr_node

        # deal with reroute nodes
        if isinstance(node, bpy.types.NodeReroute):
            if node.inputs['Input'].is_linked:
                socket = node.inputs['Input'].links[0].from_socket
                node = node.inputs['Input'].links[0].from_node
            else:
                log.warn("Reroute node '{}'.'{}' is disconnected".format(self.material.name, node.name))
                return None


        # TODO: discuss about using rules to parse nodes
        # Can we export node using rules?
        if isinstance(node, RPRShadingNode):
            return node.export(node, socket, self)

        elif node.bl_idname in blender_node_parsers:
            node_parser = blender_node_parsers[node.bl_idname](self, node)
            return node_parser.export(socket)

        log.warn("Ignoring unsupported node of type {}, '{}'.'{}'".format(type(node).__name__, self.material.name, node.name))
        return None

    def create_rpr_node(self, node_type, key):
        rpr_val = get_rpr_val(node_type)
        
        if "RPRX_" in node_type:
            return self.rpr_context.create_x_material_node(key, rpr_val)
        elif "RPR_" in node_type:
            return self.rpr_context.create_material_node(key, rpr_val)
        log.warn("Unknown RPR node type unsupported node", self.material, node_type)


