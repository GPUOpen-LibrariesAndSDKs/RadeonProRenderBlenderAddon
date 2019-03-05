from abc import ABCMeta, abstractmethod

import bpy
import pyrpr
import pyrprx

from rprblender.engine.context import RPRContext
from rprblender.utils import logging
log = logging.Log(tag='export.node')


class NodeParser(metaclass=ABCMeta):
    """
    This is the base class that parses a blender node.
    Subclasses should override only export() function.
    """

    def __init__(self, rpr_context: RPRContext, material: bpy.types.Material,
                 node: bpy.types.Node, socket_out: bpy.types.NodeSocket):
        self.rpr_context = rpr_context
        self.material = material
        self.node = node
        self.socket_out = socket_out

        log("init", self.material, self.node, self.socket_out)

    # INTERNAL FUNCTIONS

    def _get_node_key(self, node, socket_out):
        """ Returns key for blender node with output socket """

        return (self.material.name, node.name, socket_out.name if socket_out else None)

    def _export_node(self, node, socket_out):
        """
        Exports node with output socket.
        1. Checks if such node was already exported and returns it.
        2. Searches corresponded NodeParser class and do export through it
        """

        # check if such node is already was parsed
        rpr_node = self.rpr_context.material_nodes.get(self._get_node_key(node, socket_out), None)
        if rpr_node:
            return rpr_node

        # getting corresponded NodeParser class
        node_parser_class = get_node_parser_class(node.bl_idname)
        if node_parser_class:
            node_parser = node_parser_class(self.rpr_context, self.material, node, socket_out)
            return node_parser.export()

        log.warn("Ignoring unsupported node", node, self.material)
        return None

    def _parse_val(self, val):
        """ Turn a blender node val or default value for input into something that works well with rpr """

        if isinstance(val, (int, float)):
            return float(val)

        if len(val) in (3, 4):
            return tuple(val)

        raise TypeError("Unknown value type to pass to rpr", val)

    # HELPER FUNCTIONS
    # Child classes should use them to do their export

    @property
    def node_key(self):
        """ Returns key of current node """
        return self._get_node_key(self.node, self.socket_out)

    def get_output_default(self, socket_key):
        """ Returns default value of output socket """

        socket_out = self.node.outputs[socket_key]
        return self._parse_val(socket_out.default_value)

    def get_input_default(self, socket_key):
        """ Returns default value of input socket """

        socket_in = self.node.inputs[socket_key]
        return self._parse_val(socket_in.default_value)

    def get_input_link(self, socket_key):
        """ Returns linked parsed node or None if nothing is linked or not link is not valid """

        socket_in = self.node.inputs[socket_key]

        if socket_in.is_linked:
            link = socket_in.links[0]
            if link.is_valid:
                return self._export_node(link.from_node, link.from_socket)

            log.error("Invalid link found", link, socket_in, self.node, self.material)

        return None

    def get_input_value(self, socket_key):
        """ Returns linked node or default socket value """

        val = self.get_input_link(socket_key)
        if val is not None:
            return val

        return self.get_input_default(socket_key)

    # EXPORT FUNCTION
    @abstractmethod
    def export(self):
        """
        Main export function which should be overridable in child classes.
        Example:
            color = self.get_input_value('Color')
            normal = self.get_input_link('Normal')

            rpr_node = self.rpr_context.create_material_node(self.node_key, pyrpr.MATERIAL_NODE_REFLECTION)
            rpr_node.set_input('color', color)
            if normal is not None:
                rpr_node.set_input('normal', normal)

            return rpr_node
        """
        pass

    # ADDITIONAL ARITHMETIC NODES

    def arithmetic_node_value(self, val1, val2, op_type, use_key=False):
        def to_vec4(val):
            if isinstance(val, float):
                return (val, val, val, val)
            if len(val) == 3:
                return (*val, 1.0)
            return val

        def create_arithmetic_node():
            node = self.rpr_context.create_material_node(self.node_key if use_key else None,
                                                         pyrpr.MATERIAL_NODE_ARITHMETIC)
            node.set_input('op', op_type)
            node.set_input('color0', val1)
            if val2 is not None:
                node.set_input('color1', val2)  # val2 could be None

            return node

        if isinstance(val1, (pyrpr.MaterialNode, pyrprx.Material)) or isinstance(val2, (pyrpr.MaterialNode, pyrprx.Material)):
            return create_arithmetic_node()

        val1 = to_vec4(val1)
        val2 = to_vec4(val2)

        if op_type == pyrpr.MATERIAL_NODE_OP_MUL:
            return (val1[0] * val2[0], val1[1] * val2[1], val1[2] * val2[2], val1[3] * val2[3])

        if op_type == pyrpr.MATERIAL_NODE_OP_SUB:
            return (val1[0] - val2[0], val1[1] - val2[1], val1[2] - val2[2], val1[3] - val2[3])

        if op_type == pyrpr.MATERIAL_NODE_OP_ADD:
            return (val1[0] + val2[0], val1[1] + val2[1], val1[2] + val2[2], val1[3] + val2[3])

        if op_type == pyrpr.MATERIAL_NODE_OP_MAX:
            return (max(val1[0], val2[0]), max(val1[1], val2[1]), max(val1[2], val2[2]), max(val1[3], val2[3]))

        if op_type == pyrpr.MATERIAL_NODE_OP_MIN:
            return (min(val1[0], val2[0]), min(val1[1], val2[1]), min(val1[2], val2[2]), min(val1[3], val2[3]))

        return create_arithmetic_node()

    def mul_node_value(self, val1, val2, use_key=False):
        return self.arithmetic_node_value(val1, val2, pyrpr.MATERIAL_NODE_OP_MUL, use_key)

    def add_node_value(self, val1, val2, use_key=False):
        return self.arithmetic_node_value(val1, val2, pyrpr.MATERIAL_NODE_OP_ADD, use_key)

    def sub_node_value(self, val1, val2, use_key=False):
        return self.arithmetic_node_value(val1, val2, pyrpr.MATERIAL_NODE_OP_SUB, use_key)

    def max_node_value(self, val1, val2, use_key=False):
        return self.arithmetic_node_value(val1, val2, pyrpr.MATERIAL_NODE_OP_MAX, use_key)

    def min_node_value(self, val1, val2, use_key=False):
        return self.arithmetic_node_value(val1, val2, pyrpr.MATERIAL_NODE_OP_MIN, use_key)

    def dot3_node_value(self, val1, val2, use_key=False):
        return self.arithmetic_node_value(val1, val2, pyrpr.MATERIAL_NODE_OP_DOT3, use_key)

    def get_x_node_value(self, val1, use_key=False):
        return self.arithmetic_node_value(val1, None, pyrpr.MATERIAL_NODE_OP_SELECT_X, use_key)

    def get_y_node_value(self, val1, use_key=False):
        return self.arithmetic_node_value(val1, None, pyrpr.MATERIAL_NODE_OP_SELECT_Y, use_key)

    def get_z_node_value(self, val1, use_key=False):
        return self.arithmetic_node_value(val1, None, pyrpr.MATERIAL_NODE_OP_SELECT_Z, use_key)

    def get_w_node_value(self, val1, use_key=False):
        return self.arithmetic_node_value(val1, None, pyrpr.MATERIAL_NODE_OP_SELECT_W, use_key)

    def combine_node_value(self, a, b, c, use_key=False):
        """Mix values to single"""
        vX = self.mul_node_value(a, (1, 0, 0), use_key)
        vY = self.mul_node_value(b, (0, 1, 0), use_key)
        vZ = self.mul_node_value(c, (0, 0, 1), use_key)

        res = self.add_node_value(self.add_node_value(vX, vY), vZ, use_key)
        return res

    def blend_node_value(self, val1, val2, weight, use_key=False):
        node = self.rpr_context.create_material_node(self.node_key if use_key else None,
                                                     pyrpr.MATERIAL_NODE_BLEND_VALUE)
        node.set_input('color0', val1)
        node.set_input('color1', val2)
        node.set_input('weight', weight)

        return node


class RuleNodeParser(NodeParser):
    """
    Base class that parses material node by rules. It looks up inputs on the blender node and get values,
    then creates (multiple) rpr nodes from the nodes data structure. rpr_nodes can have inputs based on
    the blender node inputs, or connected to each other within the list.

    Child classes should only reassign 'nodes' class field. Example:
    nodes =  {
        "emission_color": {
            "type": "*",
            "params": {
                "color0": "inputs.Color",
                "color1": "inputs.Strength",
            }
        },
        "Emission": {
            "type": pyrpr.MATERIAL_NODE_EMISSIVE,
            "params": {
                "color": "nodes.emission_color"
            }
        }
    }
    Supported types: pyrpr.*, pyrprx.*, "*", "+", "-", "max", "min", "blend"
    Supported params: pyrpr.*, pyrprx.*, str
    Supported values: pyrpr.*, pyrprx.*, "nodes.*", "inputs.*", "link:inputs.*", "default:inputs.*"
    Note: if pyrprx.* type is used then field "is_rprx": True should be added
    """

    nodes = {}

    def _export_node_rule(self, node_rule, use_key=False):
        """ Recursively exports current node_rule """

        # getting inputs
        inputs = {}
        for key, val in node_rule['params'].items():
            if not isinstance(val, str):
                inputs[key] = val
                continue

            if val.startswith('nodes.'):
                node_rule_key = val[6:]
                inputs[key] = self._export_node_rule(self.nodes[node_rule_key])
                continue

            if val.startswith('inputs.'):
                socket_key = val[7:]
                inputs[key] = self.get_input_value(socket_key)
                continue

            if val.startswith('link:inputs.'):
                socket_key = val[12:]
                inputs[key] = self.get_input_link(socket_key)
                continue

            if val.startswith('default:inputs.'):
                socket_key = val[15:]
                inputs[key] = self.get_input_link(socket_key)
                continue

            raise ValueError("Invalid prefix for input value", key, val, node_rule)

        # creating material node
        node_key = self.node_key if use_key else None

        node_type = node_rule['type']
        if isinstance(node_type, int):
            if node_rule.get('is_rprx', False):
                rpr_node = self.rpr_context.create_x_material_node(node_key, node_type)
            else:
                rpr_node = self.rpr_context.create_material_node(node_key, node_type)

        else:
            if node_type == '*':
                return self.mul_node_value(inputs['color0'], inputs['color1'], use_key)

            if node_type == '+':
                return self.add_node_value(inputs['color0'], inputs['color1'], use_key)

            if node_type == '-':
                return self.sub_node_value(inputs['color0'], inputs['color1'], use_key)

            if node_type == 'max':
                return self.max_node_value(inputs['color0'], inputs['color1'], use_key)

            if node_type == 'min':
                return self.min_node_value(inputs['color0'], inputs['color1'], use_key)

            if node_type == 'blend':
                return self.blend_node_value(inputs['color0'], inputs['color1'], inputs['weight'], use_key)

            raise TypeError("Incorrect type of node_type", node_type)

        # setting inputs
        for key, val in inputs.items():
            if val is None:
                continue

            if key.startswith('pyrprx.'):
                key = getattr(pyrprx, key[7:])

            rpr_node.set_input(key, val)

        return rpr_node

    def export(self):
        """ Implements export functionality by rules """

        node_rule = self.nodes.get(self.socket_out.name, None)
        if not node_rule:
            log.warn("Ignoring unsupported output socket", self.socket_out, self.node, self.material)
            return None

        return self._export_node_rule(node_rule, use_key=True)


def get_node_parser_class(node_idname: str):
    """ Returns NodeParser class for node_idname or None if not found """

    from . import blender_nodes
    parser_class = getattr(blender_nodes, node_idname, None)
    if parser_class:
        return parser_class

    from . import rpr_nodes
    return getattr(rpr_nodes, node_idname, None)
