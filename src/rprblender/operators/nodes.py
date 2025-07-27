#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
from collections import defaultdict
from bpy.props import FloatProperty, EnumProperty, StringProperty

from rprblender.utils import BLENDER_VERSION
from rprblender.utils.user_settings import get_user_settings
from . import RPR_Operator
from rprblender.export.material import get_material_output_node
from rprblender.utils.logging import Log
import math 
import bpy
from rprblender.nodes.node_parser import get_node_parser_class

log = Log(tag='material.nodes.operator', level='info')


def bake_nodes(node_tree, nodes, material, resolution, obj):
    ''' bakes all nodes to a texture of resolution and makes texture nodes to replace them '''
    ''' TODO this could possibly be made faster by doing in multiple subproceses '''
    # setup
    bpy.context.view_layer.objects.active = obj
    obj.active_material = material

    # find output node
    output_node = get_material_output_node(material)
    surface_socket = output_node.inputs['Surface']
    surface_node = surface_socket.links[0].from_node if surface_socket.is_linked else None

    # create emission node and hookup.  Emission node is needed to bake through
    emission_node = node_tree.nodes.new(type='ShaderNodeEmission')
    node_tree.links.new(emission_node.outputs[0], surface_socket)

    # for each selected node create a texture and bake
    for node in nodes:
        for output in node.outputs:
            # only bake connected outputs
            if not output.is_linked:
                continue

            # create texture node if not already one
            baked_texture_node_name = node.name + " Baked " + output.name
            if hasattr(node, 'rpr_baked_node_name') \
                    and node.rpr_baked_node_name == baked_texture_node_name \
                    and node.rpr_baked_node_name in node_tree.nodes:
                texture_node = node_tree.nodes[node.rpr_baked_node_name]
            else:
                texture_node = node_tree.nodes.new(type='ShaderNodeTexImage')
                texture_node.location = [node.location[0], node.location[1] - node.height]
                texture_node.name = node.name + " Baked " + output.name

                # create input texture
                image = bpy.data.images.new(name=texture_node.name, width=resolution, height=resolution)
                texture_node.image = image

            # hookup node to emission
            temp_link = node_tree.links.new(output, emission_node.inputs[0])

            # bake
            node_tree.nodes.active = texture_node
            bpy.context.scene.render.engine = 'CYCLES'
            cycles_samples = bpy.context.scene.cycles.samples
            bpy.context.scene.cycles.samples = 1  # only one sample needed
            bake_succeeded = True
            try:
                bpy.ops.object.bake(type='EMIT')
            except Exception:
                bake_succeeded = False
                log.error(f"Bake of node {node.name} in material {material.name} failed.")

            bpy.context.scene.render.engine = 'RPR'
            bpy.context.scene.cycles.samples = cycles_samples

            if bake_succeeded:
                # hookup outputs
                node_tree.links.remove(temp_link)
                for link in output.links:
                    node_tree.links.new(texture_node.outputs[0], link.to_socket)
                log.info("Baked Node", node.name)

                # save setting of texture node name for reuse
                node.rpr_baked_node_name = texture_node.name

    # remove emission
    node_tree.nodes.remove(emission_node)      
    if surface_node is not None:
        node_tree.links.new(surface_node.outputs[0], surface_socket)


class RPR_NODE_OP_bake_all_nodes(RPR_Operator):
    bl_idname = "rpr.bake_all_nodes"
    bl_label = "Bake All Unsupported Nodes to Texture"
    bl_description = "Bake all mesh objects material nodes that RPR does not handle natively to textures"

    @classmethod
    def poll(cls, context):
        return super().poll(context)

    def execute(self, context):
        # iterate over all objects and find unsupported nodes
        baked_materials = []
        baked_objs = []
        selected_object = context.active_object
        selected_layer = context.window.view_layer

        for layer in context.scene.view_layers:
            context.window.view_layer = layer
            for obj in layer.objects:
                if obj.type != 'MESH' or obj.name in baked_objs:
                    continue

                baked_objs.append(obj.name)

                for material_slot in obj.material_slots:
                    if material_slot.material.name in baked_materials:
                        continue
                    nt = material_slot.material.node_tree
                    if nt is None:
                        continue

                    nodes_to_bake = []
                    for node in nt.nodes:
                        if not get_node_parser_class(node.bl_idname):
                            nodes_to_bake.append(node)

                    settings = get_user_settings()
                    resolution = settings.bake_resolution

                    old_selection = obj.select_get()
                    obj.select_set(True)
                    bake_nodes(nt, nodes_to_bake, material_slot.material, int(resolution), obj)
                    obj.select_set(old_selection)

                    baked_materials.append(material_slot.material.name)

        context.window.view_layer = selected_layer
        selected_object.select_set(True)
        return {'FINISHED'}


class RPR_NODE_OP_bake_selected_nodes(RPR_Operator):
    bl_idname = "rpr.bake_selected_nodes"
    bl_label = "Bake Selected Nodes to Texture"
    bl_description = "Bake selected nodes to Texture"

    resolution: EnumProperty(items=(('64', '64', '64'),
                              ('128', '128', '128'),
                              ('256', '256', '256'),
                              ('512', '512', '512'),
                              ('1024', '1024', '1024'),
                              ('2048', '2048', '2048'),
                              ('4096', '4096', '4096')),
                            default='2048',
                            name="Texture Resolution"
                            )       

    @classmethod
    def poll(cls, context):
        return super().poll(context) and context.object \
               and context.object.active_material and context.object.active_material.node_tree

    def execute(self, context):
        space = context.space_data
        nt = space.node_tree
        nodes_selected = context.selected_nodes

        settings = get_user_settings()
        resolution = settings.bake_resolution

        bake_nodes(nt, nodes_selected, context.material, int(resolution), bpy.context.active_object)

        return {'FINISHED'}


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
    bl_description = "Converts Principled BSDF to RPR Uber for all materials"

    @classmethod
    def poll(cls, context):
        # This operator can always be run, as it iterates through all materials.
        return super().poll(context)

    def execute(self, context):
        def convert_principled_to_uber_for_material(material):
            nt = material.node_tree
            if nt is None:
                return

            output_node = get_material_output_node(material)
            if not output_node: # Handle cases where a material might not have an output node
                return

            surface_socket = output_node.inputs['Surface']

            if surface_socket.is_linked and \
                    surface_socket.links[0].from_node.bl_idname == 'ShaderNodeBsdfPrincipled':
                principled_node = surface_socket.links[0].from_node
            else:
                return

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
                    # Special handling for 'Color' input of Invert node, ensure it's a sequence
                    if new_socket.bl_idname == 'NodeSocketColor' and isinstance(original_socket.default_value, float):
                        new_socket.default_value = (original_socket.default_value, original_socket.default_value, original_socket.default_value, 1.0)
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
            if enabled('Coat Weight' if BLENDER_VERSION >= "4.0" else 'Clearcoat'):
                uber_node.enable_coating = True
                # weight and color are already 1
                copy_input(principled_node.inputs['Coat Weight' if BLENDER_VERSION >= "4.0" else 'Clearcoat'], uber_node.inputs['Coating Weight'])
                copy_input(principled_node.inputs['Coat Roughness' if BLENDER_VERSION >= "4.0" else 'Clearcoat Roughness'], uber_node.inputs['Coating Roughness'])
                copy_input(principled_node.inputs['IOR'], uber_node.inputs['Coating IOR'])

            # sheen 
            if enabled('Sheen Weight' if BLENDER_VERSION >= "4.0" else 'Sheen'):
                uber_node.enable_sheen = True
                # weight and color are already 1
                copy_input(principled_node.inputs['Sheen Weight' if BLENDER_VERSION >= "4.0" else 'Sheen'], uber_node.inputs['Sheen Weight'])
                copy_input(principled_node.inputs['Base Color'], uber_node.inputs['Sheen Color'])
                copy_input(principled_node.inputs['Sheen Tint'], uber_node.inputs['Sheen Tint'])

            # normal 
            if enabled('Normal'):
                uber_node.enable_normal = True
                copy_input(principled_node.inputs['Normal'], uber_node.inputs['Normal'])
        
            # SSS
            if enabled('Subsurface Weight' if BLENDER_VERSION >= "4.0" else 'Subsurface'):
                # we don't handle max distance here
                uber_node.enable_sss = True
                copy_input(principled_node.inputs['Subsurface Weight' if BLENDER_VERSION >= "4.0" else 'Subsurface'], uber_node.inputs['Subsurface Weight'])
                copy_input(principled_node.inputs['Base Color'], uber_node.inputs['Base Color'])
                copy_input(principled_node.inputs['Subsurface Radius'], uber_node.inputs['Subsurface Radius'])

            # emission
            # Check if emission is enabled based on both color and strength
            if enabled('Emission Color' if BLENDER_VERSION >= "4.0" else 'Emission', array_type=True) or \
               enabled('Emission Strength' if BLENDER_VERSION >= "4.0" else 'Emission Strength'): # Blender 4.0 renamed 'Emission' socket to 'Emission Color' and added 'Emission Strength'
                uber_node.enable_emission = True
                uber_node.emission_doublesided = True
                copy_input(principled_node.inputs['Emission Color' if BLENDER_VERSION >= "4.0" else 'Emission'], uber_node.inputs['Emission Color'])
                # Directly copy the Emission Strength value
                copy_input(principled_node.inputs['Emission Strength'], uber_node.inputs['Emission Intensity'])
                
            if principled_node.inputs['Alpha'].default_value != 1.0:
                uber_node.enable_transparency = True
                invert_node = nt.nodes.new(type="ShaderNodeInvert")
                invert_node.location = uber_node.location
                invert_node.location[0] -= 300
                copy_input(principled_node.inputs['Alpha'], invert_node.inputs['Color'])
                nt.links.new(invert_node.outputs[0], uber_node.inputs['Transparency'])

            if enabled('Transmission Weight' if BLENDER_VERSION >= "4.0" else 'Transmission'):
                uber_node.enable_refraction = True
                invert_node = nt.nodes.new(type="ShaderNodeInvert")
                invert_node.location = uber_node.location
                invert_node.location[0] -= 300
                copy_input(principled_node.inputs['Transmission Weight' if BLENDER_VERSION >= "4.0" else 'Transmission'], invert_node.inputs['Color'])
                nt.links.new(invert_node.outputs[0], uber_node.inputs['Diffuse Weight'])

                uber_node.reflection_mode = 'PBR'
                copy_input(principled_node.inputs['IOR'], uber_node.inputs['Reflection IOR'])

                copy_input(principled_node.inputs['Transmission Weight' if BLENDER_VERSION >= "4.0" else 'Transmission'], uber_node.inputs['Refraction Weight'])
                copy_input(principled_node.inputs['Base Color'], uber_node.inputs['Refraction Color'])
                copy_input(principled_node.inputs['Roughness' if BLENDER_VERSION >= "4.0" else 'Transmission Roughness'], uber_node.inputs['Refraction Roughness'])
            
            log.info(f"Converted Principled BSDF to Uber for material: {material.name}")

        processed_materials = set()
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                for material_slot in obj.material_slots:
                    material = material_slot.material
                    if material and material.name not in processed_materials:
                        convert_principled_to_uber_for_material(material)
                        processed_materials.add(material.name)
        
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