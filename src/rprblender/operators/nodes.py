from collections import defaultdict

from bpy.props import FloatProperty

from . import RPR_Operator

from rprblender.utils.logging import Log
log = Log(tag='material.nodes.operator', level='info')


class RPR_MATERIAL_LIBRARY_OP_arrage_nodes(RPR_Operator):
    bl_idname = "rpr.arrange_material_nodes"
    bl_label = "Arrange Material Nodes"
    bl_description = "Arrange material shader nodes"

    margin_vertical: FloatProperty(default=250)
    margin_horizontal: FloatProperty(default=350)

    @classmethod
    def poll(cls, context):
        # We need active material tree to work with
        return super().poll(context) and context.object \
               and context.object.active_material and context.object.active_material.node_tree

    def execute(self, context):
        obj = context.object
        material = obj.active_material

        nodes = Nodes(material.node_tree)
        nodes.arrange(self.margin_vertical, self.margin_horizontal)

        return {'FINISHED'}


##
# NOTE: code below is a fixed copy-paste of what was used in RPR for Blender 2.7.
# It works but it's hard to understand. It also looks ugly.
# Replace it with better version when time is right.

class Node(object):
    def __init__(self, node, nodes):
        self.node = node
        self.pin = False
        self.level = 0
        self.nodes = nodes

    def __repr__(self):
        return "Node('{}')".format(self.node.name)

    def __getattr__(self, name):
        if name in ["x", "y"]:
            return getattr(self.node.location, name)
        if name in ["w", "h"]:
            name = "x" if name == "w" else "y"
            return getattr(self.node.dimensions, name)
        if name == "idname":
            return self.node.bl_idname
        return getattr(self.node, name)

    def __setattr__(self, name, value):
        if name in ["x", "y"]:
            setattr(self.node.location, name, value)
        else:
            object.__setattr__(self, name, value)

    @property
    def children(self):
        for input in self.node.inputs:
            for l in input.links:
                yield self.nodes._nodes[l.from_node.name]

    @property
    def parents(self):
        for output in self.node.outputs:
            for incoming_link in output.links:
                yield self.nodes.nodes[incoming_link.to_node.name]

    def arrange(self, margin_vertical, margin_horizontal):
        children = list(self.children)
        if len(children):
            height = sum([child.h for child in children]) + margin_vertical * (len(children) - 1.0)
            start_y = self.y - (self.h / 2.0) + height / 2.0
            start_x = self.x - margin_horizontal - max([n.w for n in children])
            for child in children:
                if not child.pin:
                    child.y = start_y
                    child.x = start_x
                    start_y -= child.h + margin_vertical
                    child.pin = True
                    child.arrange(margin_vertical, margin_horizontal)

        self.pin = True


class Nodes:
    def __init__(self, tree):
        self._tree = tree
        self._nodes = {}
        for node in tree.nodes:
            self._nodes[node.name] = Node(node, self)

        self._levels = defaultdict(lambda: [])

    def set_levels(self, node=None, level=0):
        if node is None:
            node = self.roots[0]

        for child in node.children:
            self.set_levels(child, level + 1)

        if level >= node.level:
            node.level = level

    @property
    def levels(self):
        if not self._levels:
            for node in self._nodes.values():
                self._levels[node.level].append(node)
        return self._levels

    @property
    def active(self):
        if self._tree.nodes.active:
            return self._nodes[self._tree.nodes.active.name]

    @property
    def roots(self):
        return [output for output in self._nodes.values() if output.bl_idname == 'ShaderNodeOutputMaterial']

    def sort_levels(self, margin):
        for entry in self.levels:
            level = sorted(self.levels[entry], key=lambda x: -x.y)

            for i in range(len(level) - 1):
                node1 = level[i]
                node2 = level[i + 1]
                d = (node1.y - node1.h) - node2.y
                if d < margin:
                    node2.y = node1.y - node1.h - margin

    def arrange(self, margin_vertical, margin_horizontal):
        for roots in self.roots:
            roots.arrange(margin_vertical, margin_horizontal)

        self.set_levels()
        levels = set(node.level for node in self._nodes.values())
        for l in levels:
            d = -l * margin_horizontal + self.roots[0].x
            for node in self.levels[l]:
                node.x = d
        self.sort_levels(margin_vertical)

