import bpy
from . import logging


def log(*args):
    logging.info(*args, tag="Material")


def find_node_in_node_tree(tree, node_type):
    if not tree:
        return None
    for node in tree.nodes:
        nt = getattr(node, "bl_idname", None)
        if nt == node_type:
            return node
    return None


def find_output_node_in_tree(tree):
    res = find_node_in_node_tree(tree, 'rpr_shader_node_output')
    if not res:
        # try cycles output node
        res = find_node_in_node_tree(tree, 'ShaderNodeOutputMaterial')
    return res


def find_rpr_output_node(tree):
    return find_node_in_node_tree(tree, 'rpr_shader_node_output')


def find_cycles_output_node(tree):
    return find_node_in_node_tree(tree, 'ShaderNodeOutputMaterial')


def activate_shader_editor():
    activate_editor('ShaderNodeTree')


def activate_editor(editor):
    if editor == '':
        return False
    nodes_editor = find_node_editor(editor)
    if nodes_editor:
        try:
            nodes_editor.tree_type = editor
        except:
            return False
    return True


def get_activate_editor_name():
    if bpy.context.screen:
        for area in bpy.context.screen.areas:
            if area.type == 'NODE_EDITOR':
                for space in area.spaces:
                    if space.type == 'NODE_EDITOR':
                        return space.tree_type
    return ''


def find_node_editor(tree_type):
    nodes_editor = None
    if bpy.context.screen:
        for area in bpy.context.screen.areas:
            if area.type == 'NODE_EDITOR':
                for space in area.spaces:
                    if space.type == 'NODE_EDITOR':
                        if space.tree_type == tree_type:
                            return None
                        else:
                            nodes_editor = space
    return nodes_editor

