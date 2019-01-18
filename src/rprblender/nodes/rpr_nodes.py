import bpy
import json
import os

import bpy

from rprblender.utils import logging
# from .export import export_blender_node

''' Layout of meta data for nodes:

    {
    "node_name": {  # the node id name
        "name": "Foo Bar",  # pretty label
        
        "inputs": [ # list of inputs to the blender node itself
            {
                "name":"my_color",
                "type":"color",  # input type color, float, boolean, etc
                "label":"My Color",
                "default": [0.0, 0.0, 0.0, 1.0]
                "connectable": False # if this is a socket input or just a setting, default is connectable
            },
            ...
        ],

        "outputs": [ # list of output to the blender node.  
                    # NOTE we CAN have more than one output here as the blender node is comprised of multiple rpr nodes
            {
                "name":"color",
                "type":"color", # we want to preserve socket types for output
                "label":"Color",
                "node": "blend" # the rpr_node this output will be
                                # this will allow multiple outputs
            },
            ...
        ],

        "nodes": [
            # list of rpr_nodes to make and how to hook them up 
            {
                "name": "blend",
                "type": "RPR_MATERIAL_NODE_BLEND",  # the RPR node type
                "inputs": {
                    "RPR_MATERIAL_INPUT_COLOR0": "inputs.occluded_color",
                    "RPR_MATERIAL_INPUT_COLOR0": [1.0, 0.0, 0.0, 1.0],
                    "RPR_MATERIAL_INPUT_WEIGHT": "nodes.ao",

                    # inputs to the rpr_node can be hooked up to
                        a:  inputs.xxx, map the rpr input the blender node socket
                        b:  nodes.XXX, connect to another rpr_node
                        c:  value [x, x, x, x]
                }
                ...
            }
        ],

        
    }
}
'''


class RPRShadingNode(bpy.types.ShaderNode):  # , RPR_Properties):
    bl_compatibility = {'RPR'}
    bl_idname = 'rpr_shader_node'
    bl_label = 'RPR Shader Node'
    bl_icon = 'MATERIAL'

    # shader meta data from json
    meta_data = {
        'settings': (),
        'inputs': (),
        'outputs': (),
    }

    @staticmethod
    def get_socket(node, name=None, index=None):
        if name:
            try:
                socket = node.inputs[name]
            except KeyError:
                return None
        elif index:
            try:
                socket = node.inputs[index]
            except IndexError:
                return None
        else:
            return None

        logging.info("get_socket({}, {}, {}): {}; linked {}; links number {}".
                     format(node, name, index, socket, socket.is_linked, len(socket.links)),
                     tag="ShadingNode")
        if socket.is_linked and len(socket.links) > 0:
            return socket.links[0].from_socket
        return None

    @classmethod
    def poll(cls, tree: bpy.types.NodeTree):
        return tree.bl_idname in ('ShaderNodeTree', 'RPRTreeType') and bpy.context.scene.render.engine == 'RPR'

    def __init__(self):
        ''' generate sockets based on meta data '''
        for input in self.meta_data['inputs']:
            # add input 
            pass
        for output in self.meta_data['outputs']:
            # add output
            pass


def generate_types():
    ''' This function will walk the config directory for JSON files and 
        generate node types for each.

        Each node type generated will hold it's own connection info (just the json data really)

        These "generated" nodes will be somewhat harder to debug but give more 
        flexibilty and ease of adding new nodes.  They should create some debug output as well.
    '''
    dir_path = os.path.dirname(os.path.realpath(__file__))
    config_dir = os.path.join(dir_path, 'rpr_nodes')
    for f in os.listdir(config_dir):
        with open(os.path.join(config_dir, f), 'r') as json_file:
            print("parsing node " + f)
            json_data = json.load(json_file)
            node_name = list(json_data.keys())[0]
            type_name = "RPRShadinNode" + node_name
            type_dict = {
                'bl_idname': 'rpr_shader_node_' + type_name,
                'bl_label': 'RPR ' + json_data[node_name]['name'],
                'meta_data': json_data[node_name]
                # note that we would need to add bpy.props parameters here too
            }
            # subtype RPRShadingNode
            node_type = type(type_name, (RPRShadingNode,), type_dict)

            bpy.utils.register_class(node_type)


classes = (RPRShadingNode,)