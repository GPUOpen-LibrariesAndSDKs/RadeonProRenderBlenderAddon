import json
import os

from .export import export_blender_node

''' Layout of meta data for nodes is SAME for blender nodes as RPR ones:
'''


def convert_blender_node(blender_node):
    ''' This function gets the converter json mapping and runs the rpr conversion'''
    if not mapping:
        load_mapping()

    blender_node_name = blender_node.__name__.split('.')[-1]
    if blender_node_name not in mapping:
        print("RPR can't convert this blender node " + blender_node)
        return

    export_blender_node(blender_node, mapping[blender_node_name])



def load_mapping():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    config_dir = os.path.join(dir_path, 'blender_nodes')
    for f in os.listdir(config_dir):
        with open(os.path.join(config_dir, f), 'r') as json_file:
            mapping[os.path.splitext(f)][0] = json.load(json_file)
            node_name = json_data.keys()[0]
