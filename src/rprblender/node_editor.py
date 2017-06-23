import bpy

from rprblender.nodes import get_node_groups_by_id

shader_node_output_name = 'rpr_shader_node_output'
shader_node_cycles_output_name = 'ShaderNodeOutputMaterial'


def find_node_in_nodetree(tree, nodetype):
    for node in tree.nodes:
        nt = getattr(node, "bl_idname", None)
        if nt == nodetype:
            return node
    return None


def find_node(material, nodetype):
    if not material:
        return None

    tree = material.node_tree
    if not tree:
        return None

    return find_node_in_nodetree(tree, nodetype)


def find_output_node(material):
    if not material:
        return None

    tree = material.node_tree
    if not tree:
        return None

    return find_output_node_in_tree(tree)


def find_output_node_in_tree(tree):
    res = find_node_in_nodetree(tree, shader_node_output_name)
    if not res:
        # try cycles output node
        res = find_node_in_nodetree(tree, shader_node_cycles_output_name)

    return res


def recursive_find_output_node_in_group(tree, node_group_list):
    for node in tree.nodes:
        ng = get_node_groups_by_id(node.bl_idname)
        if ng:
            list = node_group_list
            list.append(node)
            res, ret_list = recursive_find_output_node_in_group(ng, list)
            if res:
                return res, ret_list

    return find_output_node_in_tree(tree), node_group_list


def find_output_node_in_group(material):
    if not material:
        return None, None

    tree = material.node_tree
    if not tree:
        return None, None

    return recursive_find_output_node_in_group(tree, [])
