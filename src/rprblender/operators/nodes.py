from collections import defaultdict
from bpy.props import FloatProperty
from . import RPR_Operator
from rprblender.export.material import get_material_output_node
from rprblender.utils.logging import Log
import math 

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


class RPR_MATERIAL_OP_principled_to_uber(RPR_Operator):
    ''' Creates an Uber node with the settings of the Principled node.  
        Hooks that up, but leaves the old principled Node. '''

    bl_idname = "rpr.principled_to_uber"
    bl_label = "Convert Principled To Uber"
    bl_description = "Converts Principled BSDF to RPR Uber"

    @classmethod
    def poll(cls, context):
        # We need active material tree to work with
        return super().poll(context) and context.object \
               and context.object.active_material and context.object.active_material.node_tree

    def execute(self, context):
        # get principled node
        nt = context.object.active_material.node_tree
        output_node = get_material_output_node(context.object.active_material)
        surface_socket = output_node.inputs['Surface']

        if surface_socket.is_linked and \
                surface_socket.links[0].from_node.bl_idname == 'ShaderNodeBsdfPrincipled':
            principled_node = surface_socket.links[0].from_node
        else:
            return {'FINISHED'}

        # create uber node
        uber_node = nt.nodes.new(type="RPRShaderNodeUber")

        # move uber node, principled node 
        uber_node.location = principled_node.location
        principled_node.location[1] += 600

        # connect uber node to output
        nt.links.new(surface_socket, uber_node.outputs[0])
        
        def copy_input(original_socket, new_socket):
            if original_socket.is_linked:
                original_link = original_socket.links[0]
                nt.links.new(original_link.from_socket, new_socket)

            else:
                new_socket.default_value = original_socket.default_value

        def enabled(socket_name, array_type=False):
            socket = principled_node.inputs[socket_name]
            if socket.is_linked:
                return True
            
            val = socket.default_value

            if val is None:
                return False

            if isinstance(val, float) and math.isclose(val, 0.0):
                return False

            if array_type and \
               math.isclose(val[0], 0.0) and \
               math.isclose(val[1], 0.0) and \
               math.isclose(val[2], 0.0):
                return False

            return True


        # connect/set inputs
        # diffuse enabled already   uber_node.enable_diffuse = True
        copy_input(principled_node.inputs['Base Color'], uber_node.inputs['Diffuse Color'])
        copy_input(principled_node.inputs['Roughness'], uber_node.inputs['Diffuse Roughness'])

        # reflection is already enabled
        uber_node.reflection_mode = 'METALNESS'
        copy_input(principled_node.inputs['Base Color'], uber_node.inputs['Reflection Color'])
        copy_input(principled_node.inputs['Roughness'], uber_node.inputs['Reflection Roughness'])
        copy_input(principled_node.inputs['Anisotropic'], uber_node.inputs['Reflection Anisotropy'])
        copy_input(principled_node.inputs['Anisotropic Rotation'], uber_node.inputs['Reflection Anisotropy Rotation'])

        # clearcoat
        if enabled('Clearcoat'):
            uber_node.enable_coating = True
            # weight and color are already 1
            copy_input(principled_node.inputs['Clearcoat'], uber_node.inputs['Coating Weight'])
            copy_input(principled_node.inputs['Clearcoat Roughness'], uber_node.inputs['Coating Roughness'])
            copy_input(principled_node.inputs['IOR'], uber_node.inputs['Coating IOR'])

        # sheen 
        if enabled('Sheen'):
            uber_node.enable_sheen = True
            # weight and color are already 1
            copy_input(principled_node.inputs['Sheen'], uber_node.inputs['Sheen Weight'])
            copy_input(principled_node.inputs['Base Color'], uber_node.inputs['Sheen Color'])
            copy_input(principled_node.inputs['Sheen Tint'], uber_node.inputs['Sheen Tint'])

        # normal 
        if enabled('Normal'):
            uber_node.enable_normal = True
            copy_input(principled_node.inputs['Normal'], uber_node.inputs['Normal'])
     
        # SSS
        if enabled('Subsurface'):
            # we don't handle max distance here
            uber_node.enable_sss = True
            copy_input(principled_node.inputs['Subsurface'], uber_node.inputs['Subsurface Weight'])
            copy_input(principled_node.inputs['Subsurface Color'], uber_node.inputs['Subsurface Color'])
            copy_input(principled_node.inputs['Subsurface Radius'], uber_node.inputs['Subsurface Radius'])

        # emission
        if enabled('Emission', array_type=True):
            uber_node.enable_emission = True
            uber_node.emission_doublesided = True
            copy_input(principled_node.inputs['Emission'], uber_node.inputs['Emission Color'])
            
        if principled_node.inputs['Alpha'].default_value != 1.0:
            uber_node.enable_transparency = True
            invert_node = nt.nodes.new(type="ShaderNodeInvert")
            invert_node.location = uber_node.location
            invert_node.location[0] -= 300
            copy_input(principled_node.inputs['Alpha'], invert_node.inputs['Color'])
            nt.links.new(invert_node.outputs[0], uber_node.inputs['Transparency'])

        if enabled('Transmission'):
            uber_node.enable_refraction = True
            invert_node = nt.nodes.new(type="ShaderNodeInvert")
            invert_node.location = uber_node.location
            invert_node.location[0] -= 300
            copy_input(principled_node.inputs['Transmission'], invert_node.inputs['Color'])
            nt.links.new(invert_node.outputs[0], uber_node.inputs['Diffuse Weight'])

            uber_node.reflection_mode = 'PBR'
            copy_input(principled_node.inputs['IOR'], uber_node.inputs['Reflection IOR'])

            copy_input(principled_node.inputs['Transmission'], uber_node.inputs['Refraction Weight'])
            copy_input(principled_node.inputs['Base Color'], uber_node.inputs['Refraction Color'])
            copy_input(principled_node.inputs['Transmission Roughness'], uber_node.inputs['Refraction Roughness'])
        
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

