from abc import ABCMeta, abstractmethod

import bpy
import pyrpr

from rprblender.engine.context import RPRContext
from .node_item import NodeItem

from rprblender.utils import logging
log = logging.Log(tag='export.node')


def key(material, node, socket_out, group_nodes: list) -> tuple:
    if group_nodes:
        return (material.name, node.name, socket_out.name if socket_out else None,
                tuple((e.name for e in group_nodes)))
    return (material.name, node.name, socket_out.name if socket_out else None)


class MaterialError(BaseException):
    """ Unsupported shader nodes setup """
    pass


class BaseNodeParser(metaclass=ABCMeta):
    """
    This is the base class that parses a blender node.
    Subclasses should override only export() function.
    """

    def __init__(self, rpr_context: RPRContext, material: bpy.types.Material,
                 node: bpy.types.Node, socket_out: bpy.types.NodeSocket,
                 group_nodes=()):
        self.rpr_context = rpr_context
        self.material = material
        self.node = node
        self.socket_out = socket_out
        # group nodes containing this node in depth, starting from upper level down to current
        # will need it to get out of each group
        self.group_nodes = group_nodes

    # INTERNAL FUNCTIONS

    def _export_node(self, node, socket_out, group_node=None):
        """
        Exports node with output socket.
        1. Checks if such node was already exported and returns it.
        2. Searches corresponded NodeParser class and do export through it
        3. Store group node reference if new one passed
        """
        # Keep reference for group node if present
        if group_node:
            if self.group_nodes:
                group_nodes = self.group_nodes + tuple([group_node])
            else:
                group_nodes = tuple([group_node])
        else:
            group_nodes = self.group_nodes

        # check if this node was already parsed
        rpr_node = self.rpr_context.material_nodes.get(
            key(self.material, node, socket_out, group_nodes),
            None)
        if rpr_node:
            return rpr_node

        # getting corresponded NodeParser class
        node_parser_class = get_node_parser_class(node.bl_idname)
        if node_parser_class:
            node_parser = node_parser_class(self.rpr_context, self.material, node, socket_out,
                                            group_nodes)
            return node_parser.final_export()

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

    def get_output_default(self, socket_key=None):
        """ Returns default value of output socket """

        socket_out = self.socket_out if socket_key is None else self.node.outputs[socket_key]
        return self._parse_val(socket_out.default_value)

    def get_input_default(self, socket_key):
        """ Returns default value of input socket """

        socket_in = self.node.inputs[socket_key]
        return self._parse_val(socket_in.default_value)

    def get_input_link(self, socket_key: [str, int], accepted_type=None):
        """
        Returns linked parsed node or None if nothing is linked or not link is not valid
        :arg socket_key: socket name to parse in current node
        :arg accepted_type: accepted types result filter, optional
        :type accepted_type: class, tuple or None
        """

        socket_in = self.node.inputs[socket_key]

        if socket_in.is_linked:
            link = socket_in.links[0]

            # check if linked is correct
            if not self.is_link_allowed(link):
                raise MaterialError("Invalid link found", link, socket_in, self.node, self.material)

            result = self._export_node(link.from_node, link.from_socket)

            # check if result type is allowed by acceptance filter
            if accepted_type and not isinstance(result, accepted_type):
                return None

            return result

        return None

    def get_input_normal(self, socket_key):
        """ Parse link, accept only RPR core material nodes """
        return self.get_input_link(socket_key, accepted_type=pyrpr.MaterialNode)

    @staticmethod
    def is_link_allowed(link):
        """
        Check if linked socket could be linked to destination socket
        Some links are not allowed for RPR, like any shader to non-shader
        """

        # link loop
        if not link.is_valid:
            return False

        source = link.from_socket
        destination = link.to_socket

        is_source_shader = isinstance(source, bpy.types.NodeSocketShader)
        is_destination_shader = isinstance(destination, bpy.types.NodeSocketShader)

        # Linking shaders and non-shaders
        if is_source_shader ^ is_destination_shader:
            return False

        return True

    def get_input_value(self, socket_key):
        """ Returns linked node or default socket value """

        val = self.get_input_link(socket_key)
        if val is not None:
            return val

        return self.get_input_default(socket_key)

    def get_input_scalar(self, socket_key):
        """ Parse link, accept only RPR core material nodes """
        val = self.get_input_link(socket_key, accepted_type=(float, tuple))
        if val is not None:
            return val

        return self.get_input_default(socket_key)

    def create_node(self, material_type, inputs={}):
        rpr_node = self.rpr_context.create_material_node(material_type)
        for name, value in inputs.items():
            rpr_node.set_input(name, value)

        return rpr_node

    def create_arithmetic(self, op_type, color1, color2=None, color3=None):
        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_ARITHMETIC, {
            'op': op_type,
            'color0': color1
        })
        if color2:
            rpr_node.set_input('color1', color2)
        if color3:
            rpr_node.set_input('color2', color3)

        return rpr_node

    # EXPORT FUNCTION
    @abstractmethod
    def export(self):
        """
        Main export function which should be overridable in child classes.
        Example:
            color = self.get_input_value('Color')
            normal = self.get_input_link('Normal')

            node = self.create_node(pyrpr.MATERIAL_NODE_REFLECTION, {
                'color': color
            })
            if normal:
                node.set_input('normal', normal)

            return node
        """
        pass

    def final_export(self):
        """
        This is the entry point of NodeParser classes.
        This function does some useful preparation before and after calling export() function.
        """

        log("export", self.material, self.node, self.socket_out, self.group_nodes)
        rpr_node = self.export()

        if isinstance(rpr_node, pyrpr.MaterialNode):
            node_key = key(self.material, self.node, self.socket_out, self.group_nodes)
            self.rpr_context.set_material_node_key(node_key, rpr_node)
            rpr_node.set_name(str(node_key))

        return rpr_node


class NodeParser(BaseNodeParser):
    """
    This class provides socket data through NodeItem class for easily do mathematical operations.
    Overridable export() function in child classes should return value through NodeItem or None.
    """
    def final_export(self):
        """
        This is the entry point of NodeParser classes.
        This function does some useful preparation before and after calling export() function.
        """

        log("export", self.material, self.node, self.socket_out, self.group_nodes)
        node_item = self.export()
        rpr_node = node_item.data if node_item else None

        if isinstance(rpr_node, pyrpr.MaterialNode):
            node_key = key(self.material, self.node, self.socket_out, self.group_nodes)
            self.rpr_context.set_material_node_key(node_key, rpr_node)
            rpr_node.set_name(str(node_key))

        return rpr_node

    @abstractmethod
    def export(self) -> [NodeItem, None]:
        pass

    def get_output_default(self, socket_key=None) -> NodeItem:
        val = super().get_output_default(socket_key)
        return self.node_item(val)

    def get_input_default(self, socket_key) -> NodeItem:
        val = super().get_input_default(socket_key)
        return self.node_item(val)

    def get_input_link(self, socket_key, accepted_type=None) -> [NodeItem, None]:
        val = super().get_input_link(socket_key, accepted_type)
        if val is None:
            return None

        return self.node_item(val)

    def create_node(self, material_type, inputs={}) -> NodeItem:
        val = super().create_node(material_type)
        for name, value in inputs.items():
            val.set_input(name, value.data if isinstance(value, NodeItem) else value)

        return self.node_item(val)

    def node_item(self, val):
        return NodeItem(self.rpr_context, val)


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
    Supported types: pyrpr.*, "*", "+", "-", "max", "min", "blend"
    Supported params: pyrpr.*, str
    Supported values: pyrpr.*, "nodes.*", "inputs.*", "link:inputs.*", "default:inputs.*"
    """

    nodes = {}

    def __init__(self, rpr_context, material, node, socket_out, group_nodes=()):
        super().__init__(rpr_context, material, node, socket_out, group_nodes)

        # internal cache of parsed node rules
        self._parsed_node_rules = {}

    def _export_node_rule_by_key(self, node_rule_key):
        if node_rule_key not in self._parsed_node_rules:
            self._parsed_node_rules[node_rule_key] = self._export_node_rule(self.nodes[node_rule_key])

        return self._parsed_node_rules[node_rule_key]

    def _export_node_rule(self, node_rule):
        """ Recursively exports current node_rule """

        if 'warn' in node_rule:
            log.warn(node_rule['warn'], self.socket_out, self.node, self.material)

        # getting inputs
        inputs = {}
        for key, val in node_rule['params'].items():
            if not isinstance(val, str):
                inputs[key] = val
                continue

            if val.startswith('nodes.'):
                node_rule_key = val[6:]
                inputs[key] = self._export_node_rule_by_key(node_rule_key)
                continue

            if val.startswith('inputs.'):
                socket_key = val[7:]
                inputs[key] = self.get_input_value(socket_key)
                continue

            if val.startswith('link:inputs.'):
                socket_key = val[12:]
                inputs[key] = self.get_input_link(socket_key)
                continue

            if val.startswith('normal:inputs.'):
                socket_key = val[14:]
                inputs[key] = self.get_input_normal(socket_key)
                continue

            if val.startswith('default:inputs.'):
                socket_key = val[15:]
                inputs[key] = self.get_input_default(socket_key)
                continue

            raise ValueError("Invalid prefix for input value", key, val, node_rule)

        # creating material node
        node_type = node_rule['type']
        if isinstance(node_type, int):
            rpr_node = self.create_node(node_type)

        else:
            if node_type == '*':
                return inputs['color0'] * inputs['color1']

            if node_type == '+':
                return inputs['color0'] + inputs['color1']

            if node_type == '-':
                return inputs['color0'] - inputs['color1']

            if node_type == 'max':
                return inputs['color0'].max(inputs['color1'])

            if node_type == 'min':
                return inputs['color0'].min(inputs['color1'])

            if node_type == 'blend':
                return inputs['weight'].blend(inputs['color0'], inputs['color1'])

            raise TypeError("Incorrect type of node_type", node_type)

        # setting inputs
        for key, val in inputs.items():
            if val is None:
                continue

            rpr_node.set_input(key, val)

        return rpr_node

    def export(self):
        """ Implements export functionality by rules """

        if self.socket_out.name not in self.nodes:
            log.warn("Ignoring unsupported output socket", self.socket_out, self.node, self.material)
            return None

        return self._export_node_rule_by_key(self.socket_out.name)


def get_node_parser_class(node_idname: str):
    """ Returns NodeParser class for node_idname or None if not found """

    from . import blender_nodes
    parser_class = getattr(blender_nodes, node_idname, None)
    if parser_class:
        return parser_class

    from . import rpr_nodes
    rpr_shader_node = getattr(rpr_nodes, node_idname, None)
    if rpr_shader_node:
        return rpr_shader_node.Exporter

    return None
