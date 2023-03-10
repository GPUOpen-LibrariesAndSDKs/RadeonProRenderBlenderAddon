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
import math
from collections import OrderedDict
import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    StringProperty,
    IntProperty
)
import mathutils
import pyrpr

from .node_parser import NodeParser, RuleNodeParser
from .blender_nodes import SSS_MIN_RADIUS, COLOR_GAMMA, ERROR_IMAGE_COLOR

from rprblender.export import image as image_export
from rprblender.export import object, light

from rprblender.utils import logging, BLENDER_VERSION
log = logging.Log(tag='export.rpr_nodes')


class RPRShaderNode(bpy.types.ShaderNode):
    """
    Base class for RPR shader nodes. Subclasses should override:
    - def init(self, context)
    This class is an example of how other RPR shaders should be looked like.
    It should override:
    - def init(self, context) - to create input and output sockets
    - def draw_buttons(self, context, layout) - if we need to draw something
    - internal class Exporter(inherited from NodeParser or RuleNodeParser) - to do export

    See as an example RPRShaderNodeDiffuse
    """

    bl_compatibility = {'RPR'}
    bl_icon = 'MATERIAL'

    @classmethod
    def poll(cls, tree: bpy.types.NodeTree):
        return tree.bl_idname in ('ShaderNodeTree', 'RPRTreeType') and bpy.context.scene.render.engine == 'RPR'


# # Layered shaders nodes
class RPRShaderNodeLayered(RPRShaderNode):
    bl_label = 'RPR Layered Shader'
    MAX_LAYERS_NUMBER = 8

    def on_layers_number_changed(self, context):
        """ Update enabled inputs by selected layers number """
        for i in range(0, self.layers_number):
            self.inputs[f'Layer {i+1}'].enabled = True
            self.inputs[f'Layer {i+1} alpha'].enabled = True
        for i in range(self.layers_number, self.MAX_LAYERS_NUMBER):
            self.inputs[f'Layer {i+1}'].enabled = False
            self.inputs[f'Layer {i+1} alpha'].enabled = False

    # number of layers, [1..MAX_LAYERS_NUMBER]
    layers_number: IntProperty(
        min=1, max=MAX_LAYERS_NUMBER, default=1,
        name="Number of layers",
        update=on_layers_number_changed
    )

    def init(self, context):
        self.outputs.new('NodeSocketShader', 'Shader')

        self.inputs.new('NodeSocketShader', f'Base Shader')

        for i in range(0, self.MAX_LAYERS_NUMBER):
            self.inputs.new('NodeSocketShader', f'Layer {i+1}').hide_value = True
            self.inputs.new('rpr_socket_weight', f'Layer {i+1} alpha').default_value = 0.5

        self.on_layers_number_changed(context)

    def draw_buttons(self, context, layout):
        layout.prop(self, 'layers_number')

    class Exporter(NodeParser):
        def export(self):
            result = self.get_input_link("Base Shader")

            if result:  # no blending with absent base shader
                for i in range(self.node.layers_number):
                    fac = self.get_input_value(f'Layer {i+1} alpha')
                    layer = self.get_input_link(f'Layer {i+1}')

                    if layer:
                        result = self.create_node(pyrpr.MATERIAL_NODE_BLEND, {
                            pyrpr.MATERIAL_INPUT_WEIGHT: fac,
                            pyrpr.MATERIAL_INPUT_COLOR0: result,
                            pyrpr.MATERIAL_INPUT_COLOR1: layer,
                        })

            return result


# # Layered texture nodes
class RPRTextureNodeLayered(RPRShaderNode):
    """ Single node to create mix of several weighted textures """
    bl_label = 'RPR Layered Texture'
    bl_width_min = 260
    MAX_LAYERS_NUMBER = 8

    MIX_ENUM = (
        ('MIX', "Mix", ""),
        ('ADD', "Add", ""),
        ('MULTIPLY', "Multiply", ""),
        ('SUBTRACT', "Subtract", ""),
        ('DIVIDE', "Divide", ""),
        ('DIFFERENCE', "Difference", ""),
        ('DARKEN', "Darken", ""),
    )

    mix_layer_0: EnumProperty(
        name=f"Layer 1 blend mode", description=f"Layer 1 blend mode",
        items=MIX_ENUM, default='MIX',
    )

    mix_layer_1: EnumProperty(
        name=f"Layer 2 blend mode", description=f"Layer 2 blend mode",
        items=MIX_ENUM, default='MIX',
    )

    mix_layer_2: EnumProperty(
        name=f"Layer 3 blend mode", description=f"Layer 3 blend mode",
        items=MIX_ENUM, default='MIX',
    )

    mix_layer_3: EnumProperty(
        name=f"Layer 4 blend mode", description=f"Layer 4 blend mode",
        items=MIX_ENUM, default='MIX',
    )

    mix_layer_4: EnumProperty(
        name=f"Layer 5 blend mode", description=f"Layer 5 blend mode",
        items=MIX_ENUM, default='MIX',
    )

    mix_layer_5: EnumProperty(
        name=f"Layer 6 blend mode", description=f"Layer 6 blend mode",
        items=MIX_ENUM, default='MIX',
    )

    mix_layer_6: EnumProperty(
        name=f"Layer 7 blend mode", description=f"Layer 7 blend mode",
        items=MIX_ENUM, default='MIX',
    )

    mix_layer_7: EnumProperty(
        name=f"Layer 8 blend mode", description=f"Layer 8 blend mode",
        items=MIX_ENUM, default='MIX',
    )

    def on_layers_number_changed(self, context):
        """ Update enabled inputs by selected layers number """
        for i in range(0, self.layers_number):
            self.inputs[f'Layer {i+1}'].enabled = True
            self.inputs[f'Layer {i+1} alpha'].enabled = True
        for i in range(self.layers_number, self.MAX_LAYERS_NUMBER):
            self.inputs[f'Layer {i+1}'].enabled = False
            self.inputs[f'Layer {i+1} alpha'].enabled = False

    # number of layers, [1..MAX_LAYERS_NUMBER]
    layers_number: IntProperty(
        min=1, max=MAX_LAYERS_NUMBER, default=1,
        name="Number of layers",
        update=on_layers_number_changed
    )

    def init(self, context):
        self.outputs.new('rpr_socket_color', 'Color')

        self.inputs.new('rpr_socket_color', f'Base Texture')

        for i in range(0, self.MAX_LAYERS_NUMBER):
            self.inputs.new('rpr_socket_color', f'Layer {i+1}')
            self.inputs.new('rpr_socket_weight', f'Layer {i+1} alpha').default_value = 0.5

        self.on_layers_number_changed(context)

    def draw_buttons(self, context, layout):
        row = layout.row()
        layout.use_property_split = True
        layout.use_property_decorate = False

        row.prop(self, 'layers_number')

        for i in range(self.layers_number):
            layout.prop(self, f"mix_layer_{i}")

    class Exporter(NodeParser):
        def export(self):
            result = self.get_input_value("Base Texture")

            for i in range(self.node.layers_number):
                fac = self.get_input_value(f'Layer {i+1} alpha')
                layer = self.get_input_value(f'Layer {i+1}')

                blend_type = getattr(self.node, f"mix_layer_{i}")
                if blend_type == 'MIX':
                    result = fac.blend(result, layer)
                elif blend_type == 'ADD':
                    result = fac.blend(result, result + layer)
                elif blend_type == 'MULTIPLY':
                    result = fac.blend(result, result * layer)
                elif blend_type == 'SUBTRACT':
                    result = fac.blend(result, result - layer)
                elif blend_type == 'DIVIDE':
                    result = fac.blend(result, result / layer)
                elif blend_type == 'DIFFERENCE':
                    result = fac.blend(result, abs(result - layer))
                elif blend_type == 'DARKEN':
                    result = fac.blend(result, result.min(layer))

            return result


# # regular shader nodes

class RPRShaderNodeDiffuse(RPRShaderNode):

    bl_label = 'RPR Diffuse'

    def init(self, context):
        # Adding input sockets with default_value or hide_value properties.
        # Here we use Blender's native node sockets
        self.inputs.new('NodeSocketColor', "Color").default_value = (0.8, 0.8, 0.8, 1.0)    # Corresponds to Cycles diffuse
        self.inputs.new('NodeSocketFloatFactor', "Roughness").default_value = 1.0
        self.inputs.new('NodeSocketVector', "Normal").hide_value = True

        # adding output socket
        self.outputs.new('NodeSocketShader', "Shader")

    class Exporter(RuleNodeParser):
        nodes = {
            "Shader": {
                "type": pyrpr.MATERIAL_NODE_DIFFUSE,
                "params": {
                    pyrpr.MATERIAL_INPUT_COLOR: "inputs.Color",
                    pyrpr.MATERIAL_INPUT_ROUGHNESS: "inputs.Roughness",
                    pyrpr.MATERIAL_INPUT_NORMAL: "normal:inputs.Normal"
                }
            },
            "hybrid:Shader": {
                "type": pyrpr.MATERIAL_NODE_UBERV2,
                "params": {
                    pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT: 1.0,
                    pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_COLOR: 'inputs.Color',
                    pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_ROUGHNESS: 'inputs.Roughness',
                    pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_NORMAL: 'normal:inputs.Normal',
                }
            },
        }


class RPRShaderNodePassthrough(RPRShaderNode):

    bl_label = 'RPR Passthrough'

    def init(self, context):
        # Adding input sockets with default_value or hide_value properties.
        # Here we use Blender's native node sockets
        self.inputs.new('NodeSocketColor', "Color").default_value = (0.8, 0.8, 0.8, 1.0)    # Corresponds to Cycles diffuse
        
        # adding output socket
        self.outputs.new('NodeSocketShader', "Shader")

    class Exporter(RuleNodeParser):
        nodes = {
            "Shader": {
                "type": pyrpr.MATERIAL_NODE_PASSTHROUGH,
                "params": {
                    pyrpr.MATERIAL_INPUT_COLOR: "inputs.Color"
                }
            },
            "hybrid:Shader": {
                "type": pyrpr.MATERIAL_NODE_UBERV2,
                "params": {
                    pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT: 1.0,
                    pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_COLOR: 'inputs.Color'
                }
            },
        }


class RPRShaderNodeUber(RPRShaderNode):
    bl_label = 'RPR Uber'
    bl_width_min = 250

    def set_from_principled(self, node: bpy.types.ShaderNodeBsdfPrincipled):
        """ set the inputs of this from a principled node and replace the outputs
            of principled with this """
        # TODO
        pass

    # list of parameters used for creating sockets, and changing enabled states of form:
    #   name: (socket_type, default_value, enabled buttons)
    # where enabled buttons is a tuple list of buttons needed to enable
    node_sockets = {
        'Diffuse Weight': ('rpr_socket_weight_soft', 1.0, "self.enable_diffuse"),
        'Diffuse Color': ('rpr_socket_color', (0.8, 0.8, 0.8, 1.0), "self.enable_diffuse"),  # Corresponds to Principled
        'Diffuse Roughness': ('rpr_socket_weight', 0.5, "self.enable_diffuse"),
        'Diffuse Normal': ('NodeSocketVector', None, "self.enable_diffuse and not self.diffuse_use_shader_normal"),

        'Backscatter Weight': ('rpr_socket_weight_soft', 0.0, "self.enable_diffuse"),
        'Backscatter Color': ('rpr_socket_color', (0.5, 0.5, 0.5, 1.0), "self.enable_diffuse and self.separate_backscatter_color"),

        'Reflection Weight': ('rpr_socket_weight_soft', 1.0, "self.enable_reflection"),
        'Reflection Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), "self.enable_reflection"),
        'Reflection Roughness': ('rpr_socket_weight', 0.25, "self.enable_reflection"),
        'Reflection IOR': ('rpr_socket_ior', 1.5, "self.enable_reflection and self.reflection_mode == 'PBR'"),
        'Reflection Metalness': ('rpr_socket_weight', 0.0, "self.enable_reflection and self.reflection_mode == 'METALNESS'"),
        'Reflection Anisotropy': ('rpr_socket_float_min1_max1', 0.0, "self.enable_reflection"),
        'Reflection Anisotropy Rotation': ('rpr_socket_weight', 0.0, "self.enable_reflection"),
        'Reflection Normal': ('NodeSocketVector', None, "self.enable_reflection and not self.reflection_use_shader_normal"),
        
        'Refraction Weight': ('rpr_socket_weight_soft', 1.0, "self.enable_refraction"),
        'Refraction Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), "self.enable_refraction"),
        'Refraction Roughness': ('rpr_socket_weight', 0.0, "self.enable_refraction"),
        'Refraction IOR': ('rpr_socket_ior', 1.5, "self.enable_refraction"),
        'Refraction Absorption Distance': ('rpr_socket_float_min0_softmax10', 0.0, "self.enable_refraction"),
        'Refraction Absorption Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), "self.enable_refraction"),
        'Refraction Normal': ('NodeSocketVector', None, "self.enable_refraction and not self.refraction_use_shader_normal"),
        
        'Coating Weight': ('rpr_socket_weight_soft', 1.0, "self.enable_coating"),
        'Coating Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), "self.enable_coating"),
        'Coating Roughness': ('rpr_socket_weight', 0.01, "self.enable_coating"),
        'Coating IOR': ('rpr_socket_ior', 1.5, "self.enable_coating"),
        'Coating Thickness': ('rpr_socket_float_min0_softmax10', 0.0, "self.enable_coating"),
        'Coating Transmission Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), "self.enable_coating"),
        'Coating Normal': ('NodeSocketVector', None, "self.enable_coating and not self.coating_use_shader_normal"),
    
        'Sheen Weight': ('rpr_socket_weight_soft', 1.0, "self.enable_sheen"),
        'Sheen Color': ('rpr_socket_color', (0.5, 0.5, 0.5, 1.0), "self.enable_sheen"),
        'Sheen Tint': ('rpr_socket_weight', 0.5, "self.enable_sheen"),
    
        'Emission Weight': ('rpr_socket_weight_soft', 1.0, "self.enable_emission"),
        'Emission Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), "self.enable_emission"),
        'Emission Intensity': ('rpr_socket_weight', 1.0, "self.enable_emission"),

        'Subsurface Weight': ('rpr_socket_weight_soft', 1.0, "self.enable_sss"),
        'Subsurface Color': ('rpr_socket_color', (0.436, 0.227, 0.131, 1.0), "self.enable_sss and not self.sss_use_diffuse_color"),
        'Subsurface Radius': ('NodeSocketVector', (3.67, 1.37, 0.68), "self.enable_sss"),
        'Subsurface Direction': ('rpr_socket_float_min1_max1', 0.0, "self.enable_sss"),
        
        'Normal': ('NodeSocketVector', None, "self.enable_normal"),

        'Transparency': ('rpr_socket_weight', 0.0, "self.enable_transparency"),

        # TODO: Implement displacement
        # 'Displacement': ('rpr_socket_link', None, "self.enable_displacement"),
    }

    def update_visibility(self, context):
        """ update visibility of each in list of sockets based on enabled properties """

        for socket_name, socket in self.inputs.items():
            # eval the socket enable string
            eval_string = self.node_sockets[socket_name][2]
            socket.enabled = eval(eval_string)

        if BLENDER_VERSION >= "3.1" and context:
            self.socket_value_update(context)

    enable_diffuse: BoolProperty(name="Diffuse", description="Enable Diffuse", default=True, update=update_visibility)
    diffuse_use_shader_normal: BoolProperty(name="Diffuse use shader normal", description="Use the master shader normal (disable to override)", default=True, update=update_visibility)
    separate_backscatter_color: BoolProperty(name="Separate Backscatter Color", description="Use separate backscatter color instead of diffuse color", default=False, update=update_visibility)

    enable_reflection: BoolProperty(name="Reflection", description="Enable Reflection", default=True, update=update_visibility)
    reflection_use_shader_normal: BoolProperty(name="Reflection use shader normal", description="Use the master shader normal (disable to override)", default=True, update=update_visibility)
    reflection_mode: EnumProperty(
        name="Reflection Mode",
        description="Set reflection via metalness or IOR",
        items=(('METALNESS', "Metalness", ""),
               ('PBR', "IOR", "")),
        default='METALNESS',
        update=update_visibility
    )

    enable_refraction: BoolProperty(name="Refraction", description="Enable Refraction", default=False, update=update_visibility)
    refraction_use_shader_normal: BoolProperty(name="Refraction use shader normal", description="Use the master shader normal (disable to override)", default=True, update=update_visibility)
    refraction_thin_surface: BoolProperty(name='Refraction Thin Surface', default=False)
    refraction_caustics: BoolProperty(name='Allow Caustics', default=False)

    enable_coating: BoolProperty(name="Coating", description="Enable Coating", default=False, update=update_visibility)
    coating_use_shader_normal: BoolProperty(name="Coating use shader normal", description="Use the master shader normal (disable to override)", default=True, update=update_visibility)
    
    enable_sheen: BoolProperty(name="Sheen", description="Enable Sheen", default=False, update=update_visibility)

    enable_emission: BoolProperty(name="Emission", description="Enable Emission", default=False, update=update_visibility)
    emission_doublesided: BoolProperty(name="Emission Doublesided", description="Enable emission doublesided", default=False, update=update_visibility)

    enable_sss: BoolProperty(name="Subsurface", description="Enable Subsurface", default=False, update=update_visibility)
    sss_use_diffuse_color: BoolProperty(name="Use Diffuse Color", description="Use diffuse color for subsurface color", default=False, update=update_visibility)
    sss_multiscatter: BoolProperty(name="Subsurface Multiple Scattering", description="Enable subsurface multiple scattering", default=False, update=update_visibility)
    
    enable_normal: BoolProperty(name="Normal", description="Enable Normal", default=False, update=update_visibility)   

    enable_transparency: BoolProperty(name="Transparency", description="Enable Transparency", default=False, update=update_visibility)    

    enable_displacement: BoolProperty(name="Displacement", description="Enable Displacement", default=False, update=update_visibility)

    def init(self, context):
        """ create sockets based on node_socket rules """
        
        for socket_name, socket_desc in self.node_sockets.items():
            socket_type = socket_desc[0]
            socket_default = socket_desc[1]
            
            socket = self.inputs.new(socket_type, socket_name)
            if socket_default is not None:
                socket.default_value = socket_default
            else:
                # socket_default is None only for link, so we are hiding its value
                socket.hide_value = True

        self.outputs.new('NodeSocketShader', 'Shader')

        self.update_visibility(context)

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        r = col.row(align=True)
        r.prop(self, 'enable_diffuse', toggle=True)
        r.prop(self, 'enable_reflection', toggle=True)
        r.prop(self, 'enable_refraction', toggle=True)
        r = col.row(align=True)
        r.prop(self, 'enable_coating', toggle=True)
        r.prop(self, 'enable_sheen', toggle=True)
        r.prop(self, 'enable_emission', toggle=True)
        r = col.row(align=True)
        r.prop(self, 'enable_sss', toggle=True)
        r.prop(self, 'enable_normal', toggle=True)
        r.prop(self, 'enable_transparency', toggle=True)

        col = layout.column(align=True)
        if self.enable_diffuse:
            box = col.box()
            c = box.column(align=True)
            c.prop(self, 'diffuse_use_shader_normal')
            c.prop(self, 'separate_backscatter_color')

        if self.enable_reflection:
            box = col.box()
            c = box.column(align=True)
            c.prop(self, 'reflection_use_shader_normal')
            c.prop(self, 'reflection_mode', text="")

        if self.enable_refraction:
            box = col.box()
            c = box.column(align=True)
            c.prop(self, 'refraction_use_shader_normal')
            c.prop(self, 'refraction_thin_surface')
            c.prop(self, 'refraction_caustics')

        if self.enable_coating:
            box = col.box()
            c = box.column(align=True)
            c.prop(self, 'coating_use_shader_normal')

        if self.enable_emission:
            box = col.box()
            c = box.column(align=True)
            c.prop(self, 'emission_doublesided')

        if self.enable_sss:
            box = col.box()
            c = box.column(align=True)
            c.prop(self, 'sss_use_diffuse_color')
            c.prop(self, 'sss_multiscatter')
        
    class Exporter(NodeParser):
        def export(self):
            """ export sockets to the uber param specced in self.node_sockets """

            def set_normal(normal_socket_key, use_shader_normal, rprx_input):
                normal = None
                if not use_shader_normal:
                    normal = self.get_input_normal(normal_socket_key)
                elif self.node.enable_normal:
                    normal = self.get_input_normal("Normal")

                if normal is not None:
                    rpr_node.set_input(rprx_input, normal)

            rpr_node = self.create_node(pyrpr.MATERIAL_NODE_UBERV2)

            # Diffuse
            if self.node.enable_diffuse:
                diffuse_weight = self.get_input_value('Diffuse Weight')
                diffuse_color = self.get_input_value('Diffuse Color')
                diffuse_roughness = self.get_input_value('Diffuse Roughness')
                backscatter_weight = self.get_input_value('Backscatter Weight')
                backscatter_color = self.get_input_value('Backscatter Color' if self.node.separate_backscatter_color else 'Diffuse Color')

                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT, diffuse_weight)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_COLOR, diffuse_color)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_ROUGHNESS, diffuse_roughness)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_WEIGHT, backscatter_weight)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_COLOR, backscatter_color)

                set_normal('Diffuse Normal', self.node.diffuse_use_shader_normal,
                           pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_NORMAL)

            else:
                # Only diffuse we have to disable manually, because it is enabled by default
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT, 0.0)

            # Reflection
            if self.node.enable_reflection:
                reflection_weight = self.get_input_value('Reflection Weight')
                reflection_color = self.get_input_value('Reflection Color')
                reflection_roughness = self.get_input_value('Reflection Roughness')
                reflection_anisotropy = self.get_input_value('Reflection Anisotropy')
                reflection_anisotropy_rotation = self.get_input_value('Reflection Anisotropy Rotation')

                # make it work exactly like in BSDF Principled
                reflection_anisotropy_rotation = 0.5 - (reflection_anisotropy_rotation % 1.0)

                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_WEIGHT, reflection_weight)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_COLOR, reflection_color)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ROUGHNESS,
                                   reflection_roughness)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ANISOTROPY,
                                   reflection_anisotropy)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ANISOTROPY_ROTATION,
                                   reflection_anisotropy_rotation)

                if self.node.reflection_mode == 'PBR':
                    reflection_ior = self.get_input_value('Reflection IOR')

                    rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_MODE,
                                       pyrpr.UBER_MATERIAL_IOR_MODE_PBR)
                    rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_IOR, reflection_ior)

                else:
                    reflection_metalness = self.get_input_value('Reflection Metalness')

                    rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_MODE,
                                       pyrpr.UBER_MATERIAL_IOR_MODE_METALNESS)
                    rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_METALNESS,
                                       reflection_metalness)

                set_normal('Reflection Normal', self.node.reflection_use_shader_normal,
                           pyrpr.MATERIAL_INPUT_UBER_REFLECTION_NORMAL)

            # Refraction
            if self.node.enable_refraction:
                refraction_weight = self.get_input_value('Refraction Weight')
                refraction_color = self.get_input_value('Refraction Color')
                refraction_roughness = self.get_input_value('Refraction Roughness')
                refraction_ior = self.get_input_value('Refraction IOR')
                refraction_absorption_distance = self.get_input_value('Refraction Absorption Distance')
                refraction_absorption_color = self.get_input_value('Refraction Absorption Color')

                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_WEIGHT, refraction_weight)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_COLOR, refraction_color)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_ROUGHNESS,
                                   refraction_roughness)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_IOR, refraction_ior)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_ABSORPTION_DISTANCE,
                                   refraction_absorption_distance)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_ABSORPTION_COLOR,
                                   refraction_absorption_color)

                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_THIN_SURFACE,
                                   self.node.refraction_thin_surface)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_CAUSTICS,
                                   self.node.refraction_caustics)

                set_normal('Refraction Normal', self.node.refraction_use_shader_normal,
                           pyrpr.MATERIAL_INPUT_UBER_REFRACTION_NORMAL)

            # Coating
            if self.node.enable_coating:
                coating_weight = self.get_input_value('Coating Weight')
                coating_color = self.get_input_value('Coating Color')
                coating_roughness = self.get_input_value('Coating Roughness')
                coating_thickness = self.get_input_value('Coating Thickness')
                coating_transmission_color = self.get_input_value('Coating Transmission Color')
                # remove transmission color negative values to prevent render artefacts
                coating_transmission_color_clamped = coating_transmission_color.max(0.0)

                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_WEIGHT, coating_weight)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_COLOR, coating_color)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_ROUGHNESS, coating_roughness)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_THICKNESS, coating_thickness)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_TRANSMISSION_COLOR,
                                   coating_transmission_color_clamped)

                coating_ior = self.get_input_value('Coating IOR')

                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_MODE,
                                   pyrpr.UBER_MATERIAL_IOR_MODE_PBR)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_IOR, coating_ior)

                set_normal('Coating Normal', self.node.coating_use_shader_normal,
                           pyrpr.MATERIAL_INPUT_UBER_COATING_NORMAL)

            # Sheen
            if self.node.enable_sheen:
                sheen_weight = self.get_input_value('Sheen Weight')
                sheen_color = self.get_input_value('Sheen Color')
                sheen_tint = self.get_input_value('Sheen Tint')

                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SHEEN_WEIGHT, sheen_weight)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SHEEN, sheen_color)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SHEEN_TINT, sheen_tint)

            # Emission
            if self.node.enable_emission:
                emission_weight = self.get_input_value('Emission Weight')
                emission_color = self.get_input_value('Emission Color')
                emission_intensity = self.get_input_value('Emission Intensity')

                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_EMISSION_WEIGHT, emission_weight)

                emission_color *= emission_intensity
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_EMISSION_COLOR, emission_color)

                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_EMISSION_MODE,
                    pyrpr.UBER_MATERIAL_EMISSION_MODE_DOUBLESIDED if self.node.emission_doublesided else
                    pyrpr.UBER_MATERIAL_EMISSION_MODE_SINGLESIDED)

            # Subsurface
            if self.node.enable_sss:
                sss_weight = self.get_input_value('Subsurface Weight')
                sss_color = self.get_input_value('Diffuse Color' if self.node.sss_use_diffuse_color else 'Subsurface Color')
                sss_radius = self.get_input_value('Subsurface Radius')
                sss_direction = self.get_input_value('Subsurface Direction')

                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_WEIGHT, sss_weight)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_COLOR, sss_color)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SSS_WEIGHT, sss_weight)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SSS_SCATTER_COLOR, sss_color)

                sss_radius = sss_radius.max(SSS_MIN_RADIUS)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SSS_SCATTER_DISTANCE, sss_radius)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SSS_SCATTER_DIRECTION, sss_direction)

                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SSS_MULTISCATTER, self.node.sss_multiscatter)

            # Transparency
            if self.node.enable_transparency:
                transparency = self.get_input_value('Transparency')

                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_TRANSPARENCY, transparency)

            return rpr_node


class RPRShaderNodeImageTexture(RPRShaderNode):
    """ Texture node.  Has UV input, image texture input and controls for image UV wrap and color space """
    bl_label = 'RPR Image Texture'
    bl_width_min = 235

    image: bpy.props.PointerProperty(type=bpy.types.Image)
    # color space, sRGB or linear for gamma
    color_space: bpy.props.EnumProperty(
        name='Color Space',
        items=(('LINEAR', "Linear", "Linear"),
               ('SRGB', "sRGB", "sRGB")),
        default='LINEAR')

    wrap: bpy.props.EnumProperty(
        name='Wrap Type',
        items=(
            ('REPEAT', "Repeat", "Repeating Texture"),
            ('MIRRORED_REPEAT', "Mirror", "Texture mirrors outside of 0-1"),
            ('CLAMP_TO_EDGE', "Clamp to Edge", "Clamp to Edge.  Outside of 0-1 the texture will smear."),
            ('CLAMP_ZERO', "Clamp to Black", "Clamp to Black outside of 0-1"),
            ('CLAMP_ONE', "Clamp to White", "Clamp to White outside of 0-1"),
        ),
        default='REPEAT'
    )

    def init(self, context):
        self.inputs.new('NodeSocketVector', "UV").hide_value = True

        # adding output socket
        self.outputs.new('rpr_socket_color', "Color")

    def draw_buttons(self, context, layout):
        col = layout.column()
        
        col.template_ID(self, 'image', open='image.open', new='image.new')

        col.prop(self, 'color_space', text='')
        col.prop(self, 'wrap', text='')
    
    class Exporter(NodeParser):
        def export(self):
            if not self.node.image:
                return self.node_item(ERROR_IMAGE_COLOR)

            rpr_image = image_export.sync(self.rpr_context, self.node.image, use_color_space=self.node.color_space)

            if not rpr_image:
                return self.node_item(ERROR_IMAGE_COLOR)

            image_wrap_val = getattr(pyrpr, 'IMAGE_WRAP_TYPE_' + self.node.wrap)
            rpr_image.set_wrap(image_wrap_val)

            rpr_node = self.create_node(pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, {
                pyrpr.MATERIAL_INPUT_DATA: rpr_image
            })

            uv = self.get_input_link('UV')
            if uv:
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UV, uv)

            return rpr_node


class RPRShaderNodeLookup(RPRShaderNode):
    """ Looks up geometry values """
    bl_label = 'RPR Lookup'
    bl_width_min = 170

    lookup_type: bpy.props.EnumProperty(
        name='Type',
        items=(
            ('UV', "UV", "Texture coordinates"),
            ('NORMAL', "Normal", "Normal"),
            ('POS', "Position", "World position"),
            ('INVEC', "InVec", "Incident direction"),
            ('UV1', "UV1", "Second set of texture coordinates"),
            ('P_LOCAL', "Object Position", "Object position"),
            ('VERTEX_COLOR', "Vertex Color", "Vertex Color"),
            ('RANDOM_COLOR', "Random Color", "Shape Random Color"),
            ('OBJECT_ID', "Object ID", "Object ID"),
        ),
        default='UV'
    )

    def init(self, context):
        # adding output socket
        self.outputs.new('rpr_socket_link', "Value")

    def draw_buttons(self, context, layout):
        layout.prop(self, 'lookup_type')

    class Exporter(NodeParser):
        lookup_type_to_id = {
            'UV': pyrpr.MATERIAL_NODE_LOOKUP_UV,
            'NORMAL': pyrpr.MATERIAL_NODE_LOOKUP_N,
            'POS': pyrpr.MATERIAL_NODE_LOOKUP_P,
            'INVEC': pyrpr.MATERIAL_NODE_LOOKUP_INVEC,
            'UV1': pyrpr.MATERIAL_NODE_LOOKUP_UV1,
            'P_LOCAL': pyrpr.MATERIAL_NODE_LOOKUP_P_LOCAL,
            'RANDOM_COLOR': pyrpr.MATERIAL_NODE_LOOKUP_SHAPE_RANDOM_COLOR,
            'OBJECT_ID': pyrpr.MATERIAL_NODE_LOOKUP_OBJECT_ID,
        }

        def export(self):
            if self.node.lookup_type == 'VERTEX_COLOR':
                r = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                    pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_VERTEX_VALUE0
                })
                g = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                    pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_VERTEX_VALUE1
                })
                b = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                    pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_VERTEX_VALUE2
                })
                a = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                    pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_VERTEX_VALUE3
                })
                return r.combine4(g, b, a)

            else:
                return self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                    pyrpr.MATERIAL_INPUT_VALUE: self.lookup_type_to_id[self.node.lookup_type]
                })

        def export_hybrid(self):
            if self.node.lookup_type in ('UV', 'UV1'):  # Only UV supported in Hybrid for now
                return self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                    pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV
                })

            return None


class RPRShaderProceduralUVNode(RPRShaderNode):
    """ Generates a procedural UV Node
        we use this for both shapes and triplanar
    """
    bl_label = 'RPR Procedural UV'
    bl_width_min = 260

    procedural_type: EnumProperty(
        name='Type',
        items=(('MATERIAL_NODE_UVTYPE_PLANAR', 'Plane', 'Planar projection'),
             ('MATERIAL_NODE_UVTYPE_CYLINDICAL', 'Cylinder', 'Cylindrical projection'),
             ('MATERIAL_NODE_UVTYPE_SPHERICAL', 'Sphere', 'Spherical projection'),
             ('MATERIAL_NODE_UVTYPE_PROJECT', 'Camera', 'Camera projection'),
             ('TRIPLANAR', 'Triplanar', 'Triplanar projection'),
            ),
        default='TRIPLANAR'
    )

    rotation: FloatVectorProperty(
        name="Rotation",
        default=(0.0, 0.0, 0.0),
        size=3, subtype='EULER'
    )

    scale: FloatVectorProperty(
        name="Scale",
        default=(1.0, 1.0, 1.0),
        size=3, subtype='XYZ'
    )

    origin: FloatVectorProperty(
        name="Location",
        default=(0.0, 0.0, 0.0),
        size=3, subtype='XYZ'
    )

    # only used for triplanar
    weight: FloatProperty(
        name="Blend Weight",
        default=0.0,
        description='Amount to blend edges',
    )

    # only for camera projection
    camera: StringProperty(name='camera',
                            description="Camera to project from",
                            default='')

    threshold: FloatProperty(
        name="Threshold",
        default=999999,
        description='Distance from camera to cutoff projection'
    )

    def init(self, context):
        # adding output socket
        self.outputs.new('NodeSocketVector', "Value")

    def draw_buttons(self, context, layout):
        layout.prop(self, 'procedural_type')
        # camera projection only shows camera and threshold params
        if self.procedural_type == 'MATERIAL_NODE_UVTYPE_PROJECT':
            layout.prop_search(self, 'camera', bpy.data, 'cameras')
            layout.prop(self, 'threshold')
        else:
            layout.prop(self, 'origin')
            layout.prop(self, 'rotation')
            layout.prop(self, 'scale')
            if self.procedural_type == 'TRIPLANAR':
                layout.prop(self, 'weight')

    class Exporter(NodeParser):
        def export(self):
            # node type is uv_procedural unless this is triplanar
            is_triplanar = self.node.procedural_type == 'TRIPLANAR'
            node_type = pyrpr.MATERIAL_NODE_UV_TRIPLANAR if is_triplanar else \
                        pyrpr.MATERIAL_NODE_UV_PROCEDURAL

            rpr_node = self.create_node(node_type)

            if self.node.procedural_type == 'MATERIAL_NODE_UVTYPE_PROJECT':
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UV_TYPE,
                                   getattr(pyrpr, self.node.procedural_type))

                # get camera set, if none set get from scene
                if self.node.camera:
                    camera_data = bpy.data.cameras[self.node.camera]
                    camera = next((obj for obj in bpy.data.objects if obj.data == camera_data), None)
                else:
                    camera = bpy.data.scenes[0].camera
                if not camera:  # default projection if no camera present will be "top-down at 0-0-0"
                    return rpr_node

                rpr_node.set_input(pyrpr.MATERIAL_INPUT_ORIGIN, tuple(camera.location))
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_ZAXIS, tuple(camera.matrix_world.col[2]))
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_XAXIS, tuple(camera.matrix_world.col[0]))
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UV_SCALE, tuple(camera.scale))
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_THRESHOLD, self.node.threshold)

            elif is_triplanar:
                # triplanar
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_OFFSET, tuple(self.node.origin))
                matrix = mathutils.Euler(self.node.rotation, 'XYZ').to_matrix()
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_ZAXIS, tuple(matrix.col[2]))
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_XAXIS, tuple(matrix.col[0]))
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_WEIGHT, self.node.weight)
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UV_SCALE, tuple(self.node.scale))

            else:
                # shape projection
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UV_TYPE,
                                   getattr(pyrpr, self.node.procedural_type))
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_ORIGIN, tuple(self.node.origin))
                matrix = mathutils.Euler(self.node.rotation, 'XYZ').to_matrix()
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_ZAXIS, tuple(matrix.col[2]))
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_XAXIS, tuple(matrix.col[0]))
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UV_SCALE, tuple(self.node.scale))
            
            return rpr_node

        def export_hybrid(self):
            return None

        def export_hybridpro(self):
            procedural_type = self.node.procedural_type
            if procedural_type != 'TRIPLANAR':
                log.warn("Ignoring unsupported RPR procedural type",
                         procedural_type, self.node, self.material)
                return None

            return self.export()


class RPRShaderNodeBumpMap(RPRShaderNode):
    """ Simple Bump map node with bump value and scale """
    bl_label = 'RPR Bump Map'

    def init(self, context):
        self.inputs.new('rpr_socket_link', 'Map').hide_value = True
        self.inputs.new('rpr_socket_float', 'Scale').default_value = 1.0

        # adding output socket
        self.outputs.new('rpr_socket_link', "Normal")

    class Exporter(RuleNodeParser):
        nodes = {
            "normal": {
                "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
                "params": {
                    pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_N,
                }
            },
            "bump": {
                "type": pyrpr.MATERIAL_NODE_BUMP_MAP,
                "params": {
                    pyrpr.MATERIAL_INPUT_COLOR: "normal:inputs.Map",
                    pyrpr.MATERIAL_INPUT_SCALE: "inputs.Scale",
                }
            },
            "normal_plus_bump": {
                "type": "+",
                "params": {
                    pyrpr.MATERIAL_INPUT_COLOR0: "nodes.normal",
                    pyrpr.MATERIAL_INPUT_COLOR1: "nodes.bump"
                }
            },
            "Normal": {
                "type": "blend",
                "params": {
                    pyrpr.MATERIAL_INPUT_WEIGHT: "inputs.Scale",
                    pyrpr.MATERIAL_INPUT_COLOR0: "nodes.normal",
                    pyrpr.MATERIAL_INPUT_COLOR1: "nodes.normal_plus_bump"
                }
            },
            "hybrid:Normal": None
        }


class RPRShaderNodeNormalMap(RPRShaderNode):
    """ Simple Normal map node with normal value and scale
        User can also flip vector at X(up-dow) and Y(left-right) axis """
    bl_label = 'RPR Normal Map'
    bl_width_min = 150  # to stop "Flip X" checkbox name clipping

    flip_x: bpy.props.BoolProperty(
        name='Flip X', description="Flip X coordinate", default=False
    )

    flip_y: bpy.props.BoolProperty(
        name='Flip Y', description="Flip Y coordinate", default=False
    )

    def init(self, context):
        self.inputs.new('NodeSocketVector', 'Map').hide_value = True
        self.inputs.new('rpr_socket_float', 'Scale').default_value = .1

        # adding output socket
        self.outputs.new('rpr_socket_link', "Normal")

    def draw_buttons(self, context, layout):
        row = layout.row()
        row.prop(self, 'flip_x')
        row.prop(self, 'flip_y')

    class Exporter(NodeParser):
        def export(self):
            
            normal_map = self.get_input_normal('Map')
            if not normal_map:
                return None

            scale = self.get_input_value('Scale')

            if self.node.flip_x or self.node.flip_y:
                # For flip_x the calculation is following: final_x = 1-x
                # therefore for vector map_value it would be: map_value = (1,0,0,0) + (-1,1,1,1)*map_value
                # The same calculation for Y coordinate
                mul_vector = (-1 if self.node.flip_x else 1,
                              -1 if self.node.flip_y else 1,
                              1, 1)
                add_vector = (1 if self.node.flip_x else 0,
                              1 if self.node.flip_y else 0,
                              0, 0)
                normal_map = normal_map * mul_vector + add_vector

            return self.create_node(pyrpr.MATERIAL_NODE_NORMAL_MAP, {
                pyrpr.MATERIAL_INPUT_COLOR: normal_map,
                pyrpr.MATERIAL_INPUT_SCALE: scale
            })
        
        def export_hybrid(self):
            return self.get_input_normal('Map')


class RPRShaderNodeEmissive(RPRShaderNode):
    """ Emissive node, only has a color and intensity """
    bl_label = 'RPR Emissive'

    emission_doublesided: BoolProperty(
        name="Double Sided", description="Enable double-sided emission", default=False
    )

    def init(self, context):
        self.inputs.new('rpr_socket_color', 'Color')
        self.inputs.new('rpr_socket_float', 'Intensity').default_value = 1.0

        # adding output socket
        self.outputs.new('NodeSocketShader', "Shader")

    def draw_buttons(self, context, layout):
        col = layout.column()
        col.prop(self, 'emission_doublesided')

    class Exporter(NodeParser):
        def export(self):
            color = self.get_input_value('Color')
            intensity = self.get_input_value('Intensity')

            rpr_node_emissive = self.create_node(pyrpr.MATERIAL_NODE_EMISSIVE, {
                pyrpr.MATERIAL_INPUT_COLOR: color * intensity
            })

            if self.node.emission_doublesided:
                return self.create_node(pyrpr.MATERIAL_NODE_TWOSIDED, {
                    pyrpr.MATERIAL_INPUT_FRONTFACE: rpr_node_emissive,
                    pyrpr.MATERIAL_INPUT_BACKFACE: rpr_node_emissive
                })

            return rpr_node_emissive

        def export_hybrid(self):
            color = self.get_input_value('Color')
            intensity = self.get_input_value('Intensity')

            return self.create_node(pyrpr.MATERIAL_NODE_EMISSIVE, {
                pyrpr.MATERIAL_INPUT_COLOR: color * intensity
            })


class RPRShaderNodeBlend(RPRShaderNode):
    """ Shader Blend node """
    bl_label = 'RPR Shader Blend'

    def init(self, context):
        self.inputs.new('rpr_socket_weight', 'Weight').default_value = 0.5
        self.inputs.new('NodeSocketShader', 'Shader 1')
        self.inputs.new('NodeSocketShader', 'Shader 2')

        # adding output socket
        self.outputs.new('NodeSocketShader', "Shader")

    class Exporter(NodeParser):
        def export(self):
            # Just like ShaderNodeMixShader
            weight = self.get_input_value('Weight')

            if isinstance(weight.data, float):
                socket_key = 1 if math.isclose(weight.data, 0.0) else \
                             2 if math.isclose(weight.data, 1.0) else None
                if socket_key:
                    shader = self.get_input_link(socket_key)
                    if shader:
                        return shader

                    return self.create_node(pyrpr.MATERIAL_NODE_DIFFUSE)

            shader1 = self.get_input_link(1)
            shader2 = self.get_input_link(2)

            # like the Blender Mix Shader return default gray diffuse if no shaders connected
            if not shader1 and not shader2:
                return self.create_node(pyrpr.MATERIAL_NODE_DIFFUSE)

            rpr_node = self.create_node(pyrpr.MATERIAL_NODE_BLEND, {
                pyrpr.MATERIAL_INPUT_WEIGHT: weight
            })
            if shader1:
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_COLOR0, shader1)
            if shader2:
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_COLOR1, shader2)

            return rpr_node

        def export_hybrid(self):
            weight = self.get_input_value('Weight')

            if isinstance(weight.data, float):
                socket_key = 1 if math.isclose(weight.data, 0.0) else \
                             2 if math.isclose(weight.data, 1.0) else None

                if socket_key:
                    shader = self.get_input_link(socket_key)
                    if shader:
                        return shader

                    return self.create_node(pyrpr.MATERIAL_NODE_UBERV2, {
                        pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT: 1.0,
                        pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_COLOR: (1.0, 1.0, 1.0, 1.0),
                    })

            return self.get_input_link(1)


class RPRShaderNodeDoublesided(RPRShaderNode):
    """ Doublesided node """
    bl_label = 'RPR Doublesided'

    def init(self, context):
        self.inputs.new('NodeSocketShader', 'Front')
        self.inputs.new('NodeSocketShader', 'Back')

        # adding output socket
        self.outputs.new('NodeSocketShader', "Shader")

    class Exporter(NodeParser):
        def export(self):
            shader1 = self.get_input_link(0)
            shader2 = self.get_input_link(1)

            # like the Blender Mix Shader return default gray diffuse if no shaders connected
            if not shader1 and not shader2:
                return self.create_node(pyrpr.MATERIAL_NODE_DIFFUSE)

            rpr_node = self.create_node(pyrpr.MATERIAL_NODE_TWOSIDED, {})
            if shader1:
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_FRONTFACE, shader1)
            if shader2:
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_BACKFACE, shader2)

            return rpr_node


class RPRValueNode_Math(RPRShaderNode):
    """ RPR node for all Arithmetics operations, equivalent of Math, Vector Math, RGB Mix with some nice additions.
    Display different number of input sockets for various operations. """
    bl_label = 'RPR Math'
    bl_width_min = 150  # for better fit of value type selector

    def toggle_clamp(self, context):
        if BLENDER_VERSION >= "3.1" and context:
            self.socket_value_update(context)

    def change_display_type(self, context):
        """ Change inputs display type to new node display_type mode """
        self.outputs[0].display_type = self.display_type
        for i in range(3):
            self.inputs[i].display_type = self.display_type
        if BLENDER_VERSION >= "3.1" and context:
            self.socket_value_update(context)

    def change_operation(self, context):
        """ Enable input sockets and change input names by selected operation settings """
        info = self.operations_settings[self.operation]
        params = info['params']
        for i in range(3):
            if i in params:
                self.inputs[i].enabled = True
                self.inputs[i].name = params[i]
            else:
                self.inputs[i].enabled = False
        if BLENDER_VERSION >= "3.1" and context:
            self.socket_value_update(context)

    # Operations settings:
    # (ID, {
    #    'name': name & description,
    #    'params': enabled inputs, dict of (index: input name)
    #   })
    operations_settings = OrderedDict([
        ('ABS', {
            'name': 'Abs',
            'params': {
                0: 'Value',
            },
        }),
        ('ACOS', {
            'name': 'Arccosine',
            'params': {
                0: 'Value',
            },
        }),
        ('ADD', {
            'name': 'Add',
            'params': {
                0: 'Value 1',
                1: 'Value 2',
            },
        }),
        ('ASIN', {
            'name': 'Arcsine',
            'params': {
                0: 'Value',
            },
        }),
        ('ATAN', {
            'name': 'Arctangent',
            'params': {
                0: 'Value',
            },
        }),
        ('AVERAGE', {
            'name': 'Average',
            'params': {
                0: 'Value 1',
                1: 'Value 2',
            },
        }),
        ('AVERAGE_XYZ', {
            'name': 'Average XYZ',
            'params': {
                0: 'Value',
            },
        }),
        ('COMBINE', {
            'name': 'Combine',
            'params': {
                0: 'Value 1',
                1: 'Value 2',
                2: 'Value 3',
            },
        }),
        ('COS', {
            'name': 'Cosine',
            'params': {
                0: 'Value',
            },
        }),
        ('CROSS3', {
            'name': 'Cross Product',
            'params': {
                0: 'Value 1',
                1: 'Value 2',
            },
        }),
        ('DOT3', {
            'name': 'Dot3 Product',
            'params': {
                0: 'Value 1',
                1: 'Value 2',
            },
        }),
        ('FLOOR', {
            'name': 'Floor',
            'params': {
                0: 'Value',
            },
        }),
        ('LENGTH3', {
            'name': 'Length3',
            'params': {
                0: 'Value',
            },
        }),
        ('MAX', {
            'name': 'Max',
            'params': {
                0: 'Value 1',
                1: 'Value 2',
            },
        }),
        ('MIN', {
            'name': 'Min',
            'params': {
                0: 'Value 1',
                1: 'Value 2',
            },
        }),
        ('MOD', {
            'name': 'Mod',
            'params': {
                0: 'Value 1',
                1: 'Value 2',
            },
        }),
        ('MUL', {
            'name': 'Multiply',
            'params': {
                0: 'Value 1',
                1: 'Value 2',
            },
        }),
        ('NORMALIZE3', {
            'name': 'Normalize',
            'params': {
                0: 'Value',
            },
        }),
        ('POW', {
            'name': 'Pow',
            'params': {
                0: 'Value 1',
                1: 'Value 2',
            },
        }),
        ('SELECT_X', {
            'name': 'Select X',
            'params': {
                0: 'Value',
            },
        }),
        ('SELECT_Y', {
            'name': 'Select Y',
            'params': {
                0: 'Value',
            },
        }),
        ('SELECT_Z', {
            'name': 'Select Z',
            'params': {
                0: 'Value',
            },
        }),
        ('SIN', {
            'name': 'Sine',
            'params': {
                0: 'Value',
            },
        }),
        ('SUB', {
            'name': 'Subtract',
            'params': {
                0: 'Value 1',
                1: 'Value 2',
            },
        }),
        ('TAN', {
            'name': 'Tangent',
            'params': {
                0: 'Value',
            },
        }),
        ('DIV', {
            'name': 'Divide',
            'params': {
                0: 'Value 1',
                1: 'Value 2',
            },
        }),
        ('DOT4', {
            'name': 'Dot4 Product',
            'params': {
                0: 'Value 1',
                1: 'Value 2',
            },
        }),
        ('SELECT_W', {
            'name': 'Select W',
            'params': {
                0: 'Value',
            },
        }),
        ('LOG', {
            'name': 'Log',
            'params': {
                0: 'Value',
            },
        }),
        ('SHUFFLE_YZWX', {
            'name': 'XYZW -> YZWX',
            'params': {
                0: 'Value',
            },
        }),
        ('SHUFFLE_ZWXY', {
            'name': 'XYZW -> ZWXY',
            'params': {
                0: 'Value',
            },
        }),
        ('SHUFFLE_WXYZ', {
            'name': 'XYZW -> WXYZ',
            'params': {
                0: 'Value',
            },
        }),
    ])

    def get_operations_items(settings):
        """ Convert operations settings to EnumProperty items list, using name as description """
        items = []
        indices = list(settings)
        for k in sorted(settings, key=lambda k: settings[k]['name']):
            name = settings[k]['name']
            items.append((k, name, name, indices.index(k)))
        return items

    # operation types selector
    operation: EnumProperty(
        name='Operation',
        items=get_operations_items(operations_settings),
        default='ADD',
        update=change_operation,
    )

    # Node values display type, same as in RPRSocketValue
    display_type: EnumProperty(
        name='Type',
        items=(
            ('COLOR', "Color", "Color"),
            ('FLOAT', "Float", "Float"),
            ('VECTOR', "Vector", "Vector")
        ),
        default='COLOR',
        update=change_display_type,
    )

    use_clamp: BoolProperty(
        name='Clamp',
        description='Clamp result to 0..1 range',
        default=False,
        update=toggle_clamp,
    )

    def init(self, context):
        # Note: input names could be changed when operation type changed
        self.inputs.new('rpr_socket_value', 'Value 1')
        self.inputs.new('rpr_socket_value', 'Value 2')
        self.inputs.new('rpr_socket_value', 'Value 3')

        # adding output socket
        self.outputs.new('rpr_socket_value', "Out")
        self.change_display_type(context)
        self.change_operation(context)

    def draw_buttons(self, context, layout):
        layout.prop(self, 'operation', text='')
        layout.prop(self, 'use_clamp')
        layout.prop(self, 'display_type', expand=True)

    def draw_label(self):
        info = self.operations_settings[self.operation]
        return self.bl_label + ' - ' + info['name']

    class Exporter(NodeParser):
        def export(self):
            op = self.node.operation

            # input names could be changed, use index
            value1 = self.get_input_value(0)

            # parse inputs "Value 2" and "Value 3" only when they are used by operation
            if self.node.inputs[1].enabled:
                value2 = self.get_input_value(1)
            if self.node.inputs[2].enabled:
                value3 = self.get_input_value(2)

            if op == 'ADD':
                val = value1 + value2
            elif op == 'SUB':
                val = value1 - value2
            elif op == 'MUL':
                val = value1 * value2
            elif op == 'SIN':
                val = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_SIN, value1)
            elif op == 'COS':
                val = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_COS, value1)
            elif op == 'TAN':
                val = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_TAN, value1)
            elif op == 'ASIN':
                val = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_ASIN, value1)
            elif op == 'ACOS':
                val = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_ACOS, value1)
            elif op == 'ATAN':
                val = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_ATAN, value1)
            elif op == 'DOT3':
                val = value1.dot3(value2)
            elif op == 'DOT4':
                val = value1.dot4(value2)
            elif op == 'CROSS3':
                val = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_CROSS3, value1, value2)
            elif op == 'LENGTH3':
                val = value1.length()
            elif op == 'NORMALIZE3':
                val = value1.normalize()
            elif op == 'POW':
                val = value1 ** value2
            elif op == 'MIN':
                val = value1.min(value2)
            elif op == 'MAX':
                val = value1.max(value2)
            elif op == 'FLOOR':
                val = value1.floor()
            elif op == 'MOD':
                val = value1 % value2
            elif op == 'ABS':
                val = abs(value1)
            elif op == 'SELECT_X':
                val = value1.get_channel(0)
            elif op == 'SELECT_Y':
                val = value1.get_channel(1)
            elif op == 'SELECT_Z':
                val = value1.get_channel(2)
            elif op == 'SELECT_W':
                val = value1.get_channel(3)
            elif op == 'COMBINE':
                # TODO: check if this is correct. By docs this should be (v1.x, v2.x, v1.y, v2.y), 2 arguments operation
                val = value1.combine(value2, value3)
            elif op == 'AVERAGE_XYZ':
                val = value1.average_xyz()
            elif op == 'AVERAGE':
                val = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_AVERAGE, value1, value2)
            elif op == 'DIV':
                val = value1 / value2
            elif op == 'LOG':
                val = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_LOG, value1)
            elif op == 'SHUFFLE_YZWX':
                val = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_SHUFFLE_YZWX, value1)
            elif op == 'SHUFFLE_ZWXY':
                val = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_SHUFFLE_ZWXY, value1)
            elif op == 'SHUFFLE_WXYZ':
                val = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_SHUFFLE_WXYZ, value1)
            else:
                raise ValueError("Incorrect operation", op)

            if self.node.use_clamp:
                val = val.clamp()

            return val

        def export_hybrid(self):
            op = self.node.operation
            if op in ('LOG', 'SHUFFLE_YZWX', 'SHUFFLE_ZWXY', 'SHUFFLE_WXYZ'):
                log.warn("Ignoring unsupported RPR Math operation",
                         op, self.node, self.material)
                return None

            return self.export()

        def export_hybridpro(self):
            return self.export()


class RPRShaderNodeToon(RPRShaderNode):
    ''' A toon shader using both the RPR Toon Shader and Ramp node '''
    bl_label = 'RPR Toon'
    bl_width_min = 310  # for better fit of ramp mode and linked light selector

    def ramp_mode_changed(self, context):
        ramp_three_sockets = [
            "Mid Shadow Color",
            "Mid Level",
            "Mid Level Mix",
            "Mid Color",
            "Mid Highlight Level",
            "Mid Highlight Level Mix",
            "Mid Highlight Color",
        ]

        ramp_five_sockets = [
            "Shadow Color",
            "Mid Shadow Level",
            "Mid Shadow Level Mix",
            "Highlight Level",
            "Highlight Level Mix",
            "Highlight Color",
        ]

        for socket in ramp_three_sockets:
            self.inputs[socket].enabled = self.ramp_mode in ('3_COLOR', '5_COLOR')

        for socket in ramp_five_sockets:
            self.inputs[socket].enabled = self.ramp_mode == '5_COLOR'

        # update node
        self.socket_value_update(context)

    def poll_light(self, obj):
        return obj.type == 'LIGHT' and obj.users

    mid_color_as_albedo: BoolProperty(
        name="Mid Color as Albedo",
        default=False,
        description="Show the Mid Color on Albedo AOV instead of Color",
        update=ramp_mode_changed
    )
    linked_light: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="Linked Light",
        description="Link one light from the scene to lit the material",
        update=ramp_mode_changed, poll=poll_light
    )

    ramp_mode: bpy.props.EnumProperty(
        name='Ramp Mode',
        items=(
            ('1_COLOR', "1 color", "Use solid color."),
            ('3_COLOR', "3 color", "Use three color ramp."),
            ('5_COLOR', "5 color", "Use five color ramp"),
        ),
        default='1_COLOR',
        update=ramp_mode_changed
    )

    def init(self, context):
        # Adding input sockets with default_value or hide_value properties.
        # Here we use Blender's native node sockets
        self.inputs.new('rpr_socket_color', "Color").default_value = (0.8, 0.8, 0.8, 1.0)    # Corresponds to Cycles diffuse
        self.inputs.new('rpr_socket_weight', "Roughness").default_value = 1.0
        self.inputs.new('rpr_socket_weight', "Transparency").default_value = 0.0
        self.inputs.new('NodeSocketVector', "Normal").hide_value = True

        # Adding ramp sockets
        # Shadow
        inp = self.inputs.new('rpr_socket_color', "Shadow Color")
        inp.default_value = (0.0, 0.0, 0.0, 1.0)
        inp.enabled = False

        # Mid Shadow
        inp = self.inputs.new('rpr_socket_weight', "Mid Shadow Level")
        inp.default_value = 0.2
        inp.enabled = False
        inp = self.inputs.new('rpr_socket_weight', "Mid Shadow Level Mix")
        inp.default_value = 0.05
        inp.enabled = False
        inp = self.inputs.new('rpr_socket_color', "Mid Shadow Color")
        inp.default_value = (0.0, 0.0, 0.0, 1.0)    # Corresponds to Cycles diffuse
        inp.enabled = False

        # Mid
        inp = self.inputs.new('rpr_socket_weight', "Mid Level")
        inp.default_value = 0.5
        inp.enabled = False
        inp = self.inputs.new('rpr_socket_weight', "Mid Level Mix")
        inp.default_value = 0.05
        inp.enabled = False
        inp = self.inputs.new('rpr_socket_color', "Mid Color")
        inp.default_value = (0.4, 0.4, 0.4, 1.0)    # Corresponds to Cycles diffuse
        inp.enabled = False

        # Mid Highlight
        inp = self.inputs.new('rpr_socket_weight', "Mid Highlight Level")
        inp.default_value = 0.8
        inp.enabled = False
        inp = self.inputs.new('rpr_socket_weight', "Mid Highlight Level Mix")
        inp.default_value = 0.05
        inp.enabled = False
        inp = self.inputs.new('rpr_socket_color', "Mid Highlight Color")
        inp.default_value = (0.8, 0.8, 0.8, 1.0)    # Corresponds to Cycles diffuse
        inp.enabled = False

        # Highlight
        inp = self.inputs.new('rpr_socket_weight', "Highlight Level")
        inp.default_value = 0.9
        inp.enabled = False
        inp = self.inputs.new('rpr_socket_weight', "Highlight Level Mix")
        inp.default_value = 0.05
        inp.enabled = False
        inp = self.inputs.new('rpr_socket_color', "Highlight Color")
        inp.default_value = (0.8, 0.8, 0.8, 1.0)    # Corresponds to Cycles diffuse
        inp.enabled = False

        # adding output socket
        self.outputs.new('NodeSocketShader', "Shader")

    def draw_buttons(self, context, layout):
        col = layout.column()
        col.prop(self, 'linked_light')
        col.prop(self, 'ramp_mode')

        if self.ramp_mode in ('3_COLOR', '5_COLOR'):
            col.prop(self, 'mid_color_as_albedo')

    class Exporter(RuleNodeParser):
        def export(self):
            toon_shader = self.create_node(pyrpr.MATERIAL_NODE_TOON_CLOSURE, {
                pyrpr.MATERIAL_INPUT_COLOR: self.get_input_value('Color'),
                pyrpr.MATERIAL_INPUT_ROUGHNESS: self.get_input_value('Roughness'),
            })

            normal = self.get_input_link('Normal')
            if normal:
                toon_shader.set_input(pyrpr.MATERIAL_INPUT_NORMAL, normal)

            # build the toon ramp node
            if self.node.ramp_mode in ('3_COLOR', '5_COLOR'):
                if self.node.mid_color_as_albedo:
                    toon_shader.set_input(pyrpr.MATERIAL_INPUT_MID_IS_ALBEDO, True)

                ramp = self.create_node(pyrpr.MATERIAL_NODE_TOON_RAMP, {
                    pyrpr.MATERIAL_INPUT_INTERPOLATION: pyrpr.INTERPOLATION_MODE_LINEAR,

                    # Mid Shadow
                    pyrpr.MATERIAL_INPUT_SHADOW: self.get_input_value('Mid Shadow Color'),

                    # Mid
                    pyrpr.MATERIAL_INPUT_POSITION1: self.get_input_value('Mid Level'),
                    pyrpr.MATERIAL_INPUT_RANGE1: self.get_input_value('Mid Level Mix'),
                    pyrpr.MATERIAL_INPUT_MID: self.get_input_value('Mid Color'),

                    # Mid Highlight
                    pyrpr.MATERIAL_INPUT_POSITION2: self.get_input_value('Mid Highlight Level'),
                    pyrpr.MATERIAL_INPUT_RANGE2: self.get_input_value('Mid Highlight Level Mix'),
                    pyrpr.MATERIAL_INPUT_HIGHLIGHT: self.get_input_value('Mid Highlight Color'),

                })

                if self.node.ramp_mode == '5_COLOR':
                    ramp.set_input(pyrpr.MATERIAL_INPUT_TOON_5_COLORS, True)

                    # Shadow
                    ramp.set_input(pyrpr.MATERIAL_INPUT_SHADOW2, self.get_input_value('Shadow Color'))
                    ramp.set_input(pyrpr.MATERIAL_INPUT_POSITION_SHADOW, self.get_input_value('Mid Shadow Level'))
                    ramp.set_input(pyrpr.MATERIAL_INPUT_RANGE_SHADOW, self.get_input_value('Mid Shadow Level Mix'))

                    # Highlight
                    ramp.set_input(pyrpr.MATERIAL_INPUT_POSITION_HIGHLIGHT, self.get_input_value('Highlight Level'))
                    ramp.set_input(pyrpr.MATERIAL_INPUT_RANGE_HIGHLIGHT, self.get_input_value('Highlight Level Mix'))
                    ramp.set_input(pyrpr.MATERIAL_INPUT_HIGHLIGHT2, self.get_input_value('Highlight Color'))

                toon_shader.set_input(pyrpr.MATERIAL_INPUT_DIFFUSE_RAMP, ramp)

            if self.node.linked_light:
                # now we can't set Area light (emissive object) to it but only light object
                if self.node.linked_light.data.type != 'AREA':
                    # we sync light here because there are cases
                    # the light isn't in rpr_context yet
                    rpr_light = light.sync(self.rpr_context, self.node.linked_light)
                    if rpr_light:
                        toon_shader.set_input(pyrpr.MATERIAL_INPUT_LIGHT, rpr_light)

                else:
                    log.warn(
                        "Ignoring unsupported Light type", self.node.linked_light.data.type
                    )

            transparency = self.get_input_value('Transparency')
            if not transparency.is_zero():
                transparency_node = self.create_node(
                    pyrpr.MATERIAL_NODE_TRANSPARENT, {pyrpr.MATERIAL_INPUT_COLOR: (1, 1, 1)}
                )
                toon_shader = self.create_node(
                    pyrpr.MATERIAL_NODE_BLEND, {
                        pyrpr.MATERIAL_INPUT_WEIGHT: transparency,
                        pyrpr.MATERIAL_INPUT_COLOR0: toon_shader,
                        pyrpr.MATERIAL_INPUT_COLOR1: transparency_node}
                )

            return toon_shader

        def export_hybridpro(self):
            return None
