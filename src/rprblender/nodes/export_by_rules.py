import pyrpr
import pyrprx
from rprblender.utils import logging
from . import MaterialError
from . import blender_nodes
import os, json


log = logging.Log(tag='NodeExportByRules', level='debug')


def get_node_rules():
    ''' get the possible list of nodes we can parse via ruleset 
        this looks at the JSON files in the blender_nodes dir and maps them 
        to a blender node id'''
    mapping = {}
    dir_path = os.path.dirname(os.path.realpath(__file__))
    config_dir = os.path.join(dir_path, 'blender_nodes')
    for f in os.listdir(config_dir):
        if ".json" in f:
            with open(os.path.join(config_dir, f), 'r') as json_file:
                mapping[os.path.splitext(f)[0]] = json.load(json_file)
    return mapping


def get_rpr_val(val_str: str):
    ''' turns a string such as RPR_MATERIAL_NODE_DIFFUSE into a key 
        such as pyrpr.MATERIAL_NODE_DIFFUSE '''
    rpr_val = None
    if val_str.startswith("RPR_"):
        rpr_val = getattr(pyrpr, val_str[4:], None)
    elif val_str.startswith("RPRX_"):
        rpr_val = getattr(pyrprx, val_str[5:], None)

    if not rpr_val:
        raise MaterialError("Unknown RPR value '{}'!".format(val_str))
    else:
        return rpr_val


def create_rpr_node_by_rules(rpr_context, blender_node_key, subnode_name, input_values, node_rules, input_rules):
    node_key = blender_node_key + (subnode_name,)
    if node_key in rpr_context.materials:
        return rpr_context.materials[node_key]

    node_info = node_rules.get(subnode_name, None)
    if not node_info:
        raise MaterialError("Rules not found for rpr node '{}'".format(subnode_name))

    node_type = get_rpr_val(node_info['type'])
    
    # create node
    is_uber_node = node_info['type'] == "RPRX_MATERIAL_UBER"
    if is_uber_node:
        rpr_node = rpr_context.create_x_material_node(node_key, node_type)
    else:
        rpr_node = rpr_context.create_material_node(node_key, node_type)

    # filling node inputs
    for input_name, value_source in node_info['inputs'].items():
        if is_uber_node:
            input_id = get_rpr_val(input_name)
            input_name = input_id

        # is it the value source name?
        if isinstance(value_source, str):
            # static info
            if value_source.startswith('inputs.'):
                target_name = value_source.split('inputs.')[1]
                if target_name in input_values:
                    value = input_values[target_name]

                    # if this input is a connection only input check that it is not a value
                    input_info = input_rules[target_name]
                    if input_info.get('connection_only', False) and not isinstance(value, pyrpr.MaterialNode):
                        log.debug("Skipping input {}.{}: connection only input not connected".format(blender_node_key, target_name))
                        continue
                else:
                    log.warn("[{}] Input '{}' value not found!".format(subnode_name, target_name))
                    continue
            # links
            elif value_source.startswith('nodes.'):
                target_name = value_source.split('nodes.')[1]
                value = create_rpr_node_by_rules(rpr_context, blender_node_key, target_name, input_values, node_rules, input_rules)
            elif value_source.startswith('scene.'):  # for example, "scene.unit_settings.scale_length"
                # TODO add scene data access
                continue
            else:
                log.warn("Unknown RPR node '{}' input value source: {}".format(subnode_name, value_source))
                continue
        else:  # nope. Constant value
            if isinstance(value_source, (tuple, list)):
                value = tuple(value_source)
            else:  # int, float
                value = value_source

        try:
            rpr_node.set_input(input_name, value)
        except TypeError as e:
            raise MaterialError("Socket '{}' value assign error".
                                format(input_name), rpr_node, e)
    return rpr_node
