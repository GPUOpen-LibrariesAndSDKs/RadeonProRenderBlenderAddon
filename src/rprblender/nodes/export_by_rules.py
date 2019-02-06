import pyrpr
import pyrprx
from rprblender.utils import logging
from . import MaterialError
from . import blender_nodes


log = logging.Log(tag='NodeExportByRules', level='debug')


# TODO use it at nodes info/plugin loading time
node_type_ids = {
    "RPR_MATERIAL_NODE_DIFFUSE": pyrpr.MATERIAL_NODE_DIFFUSE,
    "RPR_MATERIAL_NODE_REFLECTION": pyrpr.MATERIAL_NODE_REFLECTION,
    "RPR_MATERIAL_NODE_TRANSPARENT": pyrpr.MATERIAL_NODE_TRANSPARENT,
    "RPR_MATERIAL_NODE_BLEND": pyrpr.MATERIAL_NODE_BLEND,
    "RPR_MATERIAL_NODE_ARITHMETIC": pyrpr.MATERIAL_NODE_ARITHMETIC,
    "RPR_MATERIAL_NODE_BUMP_MAP": pyrpr.MATERIAL_NODE_BUMP_MAP,
    "RPR_MATERIAL_NODE_NORMAL_MAP": pyrpr.MATERIAL_NODE_NORMAL_MAP,
    "RPRX_MATERIAL_UBER": pyrprx.MATERIAL_UBER,
}

# TODO use it at nodes info/plugin loading time
uber_input_ids = {
    "RPRX_UBER_MATERIAL_DIFFUSE_WEIGHT": pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT,
    "RPRX_UBER_MATERIAL_REFLECTION_WEIGHT": pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT,
    "RPRX_UBER_MATERIAL_REFRACTION_WEIGHT": pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT,
    "RPRX_UBER_MATERIAL_COATING_WEIGHT": pyrprx.UBER_MATERIAL_COATING_WEIGHT,
    "RPRX_UBER_MATERIAL_SHEEN_WEIGHT": pyrprx.UBER_MATERIAL_SHEEN_WEIGHT,
    "RPRX_UBER_MATERIAL_EMISSION_WEIGHT": pyrprx.UBER_MATERIAL_EMISSION_WEIGHT,
    "RPRX_UBER_MATERIAL_SSS_WEIGHT": pyrprx.UBER_MATERIAL_SSS_WEIGHT,
    "RPRX_UBER_MATERIAL_BACKSCATTER_WEIGHT": pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT,

    "RPRX_UBER_MATERIAL_DIFFUSE_COLOR": pyrprx.UBER_MATERIAL_DIFFUSE_COLOR,
    "RPRX_UBER_MATERIAL_DIFFUSE_ROUGHNESS": pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS,
    "RPRX_UBER_MATERIAL_REFLECTION_COLOR": pyrprx.UBER_MATERIAL_REFLECTION_COLOR,
    "RPRX_UBER_MATERIAL_REFLECTION_ROUGHNESS": pyrprx.UBER_MATERIAL_REFLECTION_ROUGHNESS,
    "RPRX_UBER_MATERIAL_REFLECTION_MODE": pyrprx.UBER_MATERIAL_REFLECTION_MODE,
    "RPRX_UBER_MATERIAL_REFLECTION_METALNESS": pyrprx.UBER_MATERIAL_REFLECTION_METALNESS,
    "RPRX_UBER_MATERIAL_EMISSION_COLOR": pyrprx.UBER_MATERIAL_EMISSION_COLOR,
    "RPRX_UBER_MATERIAL_EMISSION_MODE": pyrprx.UBER_MATERIAL_EMISSION_MODE,
}

rulesets = {
    'ShaderNodeBsdfDiffuse': blender_nodes.bsdf_diffuse_rules,
    'ShaderNodeEmission': blender_nodes.emission_rules,
    'ShaderNodeBsdfGlossy': blender_nodes.bsdf_glossy_rules,
    'ShaderNodeBsdfTransparent': blender_nodes.bsdf_transparent_rules,
    'ShaderNodeBump': blender_nodes.vector_bump_rules,
    'ShaderNodeNormalMap': blender_nodes.vector_normal_map_rules,
    'ShaderNodeInvert': blender_nodes.color_invert_rules,
}


def create_rpr_node_by_rules(rpr_context, blender_node_key, subnode_name, input_values, rules):
    node_key = blender_node_key + (subnode_name,)
    if node_key in rpr_context.materials:
        return rpr_context.materials[node_key]

    node_info = rules.get(subnode_name, None)
    if not node_info:
        raise MaterialError("Rules not found for rpr node '{}'".format(subnode_name))

    node_type = node_type_ids.get(node_info['type'], None)
    if not node_type:
        raise MaterialError("Unknown RPR node type '{}'!".format(node_info['type']))

    # create node
    is_uber_node = node_info['type'] == "RPRX_MATERIAL_UBER"
    if is_uber_node:
        rpr_node = rpr_context.create_x_material_node(node_key, pyrprx.MATERIAL_UBER)
    else:
        rpr_node = rpr_context.create_material_node(node_key, node_type)

    # filling node inputs
    for input_name, value_source in node_info['inputs'].items():
        if is_uber_node:
            input_id = uber_input_ids.get(input_name, None)
            if not input_id:
                raise MaterialError("Unknown Uber material node input name '{}'!".format(input_name))
            input_name = input_id

        # is it the value source name?
        if isinstance(value_source, str):
            # static info
            if value_source.startswith('inputs.'):
                target_name = value_source.split('inputs.')[1]
                if target_name in input_values:
                    value = input_values[target_name]
                else:
                    log.warn("[{}] Input '{}' value not found!".format(subnode_name, target_name))
                    continue
            # links
            elif value_source.startswith('nodes.'):
                target_name = value_source.split('nodes.')[1]
                value = create_rpr_node_by_rules(rpr_context, blender_node_key, target_name, input_values, rules)
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
