import bpy
from collections import defaultdict
from bpy.props import *
from . import rpraddon
from . import logging
from rprblender.nodes import RPRPanel, RPR_NODE_GROUP_PREFIX


class Node(object):
    def __init__(self, n, nodes):
        self._node = n
        self.pin = False
        self.level = 0
        self._nodes = nodes

    def __repr__(self):
        return "Node('%s')" % self._node.name

    def __getattr__(self, name):
        if name in ["x", "y"]:
            return getattr(self._node.location, name)
        elif name in ["w", "h"]:
            name = "x" if name == "w" else "y"
            return getattr(self._node.dimensions, name)
        elif name == "idname":
            return self._node.bl_idname
        else:
            return getattr(self._node, name)

    def __setattr__(self, name, value):
        if name in ["x", "y"]:
            setattr(self._node.location, name, value)
        else:
            object.__setattr__(self, name, value)

    @property
    def children(self):
        for input in self._node.inputs:
            for l in input.links:
                yield self._nodes._nodes[l.from_node.name]

    @property
    def parents(self):
        for output in self._node.outputs:
            for l in output.links:
                yield self._nodes._nodes[l.to_node.name]

    def arrange(self, margin_vertical, margin_horizontal):
        children = list(self.children)
        if len(children):
            height = sum([c.h for c in children]) + margin_vertical * (len(children) - 1.0)
            starty = self.y - (self.h / 2.0) + height / 2.0
            startx = self.x - margin_horizontal - max([n.w for n in children])
            for c in children:
                if not c.pin:
                    c.y = starty
                    c.x = startx
                    starty -= c.h + margin_vertical
                    c.pin = True
                    c.arrange(margin_vertical, margin_horizontal)

        self.pin = True


class Nodes:

    def is_aligned_node(self, node):
        if node.bl_idname.startswith("rpr"):
            return True
        if node.bl_idname.startswith(RPR_NODE_GROUP_PREFIX):
            return True
        if node.bl_idname in ['NodeReroute']:
            return True
        return False

    def __init__(self, tree):
        self._tree = tree
        self._nodes = {}
        for n in tree.nodes:
            if self.is_aligned_node(n):
                self._nodes[n.name] = Node(n, self)

        self._levels = defaultdict(lambda: [])


    def set_levels(self, n=None, level=0):
        if n ==  None:
            n = self.roots[0]

        for c in n.children:
            self.set_levels(c, level + 1)

        if level >= n.level:
            n.level = level

    @property
    def levels(self):
        if not self._levels:
            for n in self._nodes.values():
                self._levels[n.level].append(n)
        return self._levels

    @property
    def active(self):
        if self._tree.nodes.active:
            return self._nodes[self._tree.nodes.active.name]

    @property
    def roots(self):
        return [o for o in self._nodes.values() if o.idname == "rpr_shader_node_output"]

    def sort_levels(self, margin):
        for l in self.levels:
            level = sorted(self.levels[l], key=lambda x: -x.y)

            for i in range(len(level) - 1):

                n1 = level[i]
                n2 = level[i + 1]
                d = (n1.y - n1.h) - n2.y
                if d < margin:
                    n2.y = n1.y - n1.h - margin

    def arrange(self, margin_vertical, margin_horizontal):
        for r in self.roots:
            r.arrange(margin_vertical, margin_horizontal)

        self.set_levels()
        levels = set(n.level for n in self._nodes.values())
        for l in levels:
            d = -l * margin_vertical + self.roots[0].x
            for n in self.levels[l]:
                n.x = d
        self.sort_levels(margin_vertical)


@rpraddon.register_class
class OpNodeArrange(bpy.types.Operator):
    bl_idname = "rpr.node_arrange"
    bl_label = "RPR Node Arrange"

    margin_vertical = bpy.props.FloatProperty(default=350)
    margin_horizontal = bpy.props.FloatProperty(default=550)

    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == 'RPR' and context.object \
               and context.object.active_material and context.object.active_material.node_tree

    def execute(self, context):
        obj = context.object
        mat = obj.active_material
        nodes = Nodes(mat.node_tree)
        nodes.arrange(self.margin_vertical, self.margin_horizontal)
        return {"FINISHED"}


@rpraddon.register_class
class RPRNodeArrangePanel(RPRPanel, bpy.types.Panel):
    bl_label = "RPR Node Arrange"
    bl_context = "material"
    bl_options = {'DEFAULT_CLOSED'}
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.active_material and context.space_data.tree_type == 'RPRTreeType' \
               and RPRPanel.poll(context)

    def draw(self, context):
        self.layout.operator('rpr.node_arrange', text='Arrange')

