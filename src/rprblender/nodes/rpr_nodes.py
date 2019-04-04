import math
from collections import OrderedDict
import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
)
import pyrpr
import pyrprx

from .node_parser import NodeParser, RuleNodeParser
from .blender_nodes import SSS_MIN_RADIUS, COLOR_GAMMA, ERROR_IMAGE_COLOR

from rprblender.export import image as image_export

from rprblender.utils import logging
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
                    "color": "inputs.Color",
                    "roughness": "inputs.Roughness",
                    "normal": "link:inputs.Normal"
                }
            }
        }


class RPRShaderNodeUber(RPRShaderNode):
    bl_label = 'RPR Uber'
    bl_width_min = 250

    def set_from_principled(self, node:bpy.types.ShaderNodeBsdfPrincipled):
        ''' set the inputs of this from a principled node and replace the outputs
            of principled with this '''
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
        'Reflection Anisotropy Rotation': ('rpr_socket_angle360', 0.0, "self.enable_reflection"),
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
    emission_intensity: FloatProperty(name="Emission Intensity", description="Emission intensity", default=1.0, min=0.0)
    emission_doublesided: BoolProperty(name="Emission Doublesided", description="Enable emission doublesided", default=False, update=update_visibility)

    enable_sss: BoolProperty(name="Subsurface", description="Enable Subsurface", default=False, update=update_visibility)
    sss_use_diffuse_color: BoolProperty(name="Use Diffuse Color", description="Use diffuse color for subsurface color", default=False, update=update_visibility)
    sss_multiscatter: BoolProperty(name="Subsurface Multiple Scattering", description="Enable subsurface multiple scattering", default=False, update=update_visibility)
    
    enable_normal: BoolProperty(name="Normal", description="Enable Normal", default=False, update=update_visibility)   

    enable_transparency: BoolProperty(name="Transparency", description="Enable Transparency", default=False, update=update_visibility)    

    enable_displacement: BoolProperty(name="Displacement", description="Enable Displacement", default=False, update=update_visibility)

    def init(self, context):
        ''' create sockets based on node_socket rules '''
        
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
        col.prop(self, 'enable_diffuse', toggle=True)
        if self.enable_diffuse:
            box = col.box()
            c = box.column(align=True)
            c.prop(self, 'diffuse_use_shader_normal')
            c.prop(self, 'separate_backscatter_color')
        
        col.prop(self, 'enable_reflection', toggle=True)
        if self.enable_reflection:
            box = col.box()
            c = box.column(align=True)
            c.prop(self, 'reflection_use_shader_normal')
            c.prop(self, 'reflection_mode', text="")

        col.prop(self, 'enable_refraction', toggle=True)
        if self.enable_refraction:
            box = col.box()
            c = box.column(align=True)
            c.prop(self, 'refraction_use_shader_normal')
            c.prop(self, 'refraction_thin_surface')
            c.prop(self, 'refraction_caustics')

        col.prop(self, 'enable_coating', toggle=True)
        if self.enable_coating:
            box = col.box()
            c = box.column(align=True)
            c.prop(self, 'coating_use_shader_normal')
            
        col.prop(self, 'enable_sheen', toggle=True)

        col.prop(self, 'enable_emission', toggle=True)
        if self.enable_emission:
            box = col.box()
            c = box.column(align=True)
            c.prop(self, 'emission_doublesided')
            c.prop(self, 'emission_intensity')

        col.prop(self, 'enable_sss', toggle=True)
        if self.enable_sss:
            box = col.box()
            c = box.column(align=True)
            c.prop(self, 'sss_use_diffuse_color')
            c.prop(self, 'sss_multiscatter')

        col.prop(self, 'enable_normal', toggle=True)
        col.prop(self, 'enable_transparency', toggle=True)

    class Exporter(NodeParser):
        def export(self):
            ''' export sockets to the uber param specced in self.node_sockets '''

            def set_normal(normal_socket_key, use_shader_normal, rprx_input):
                normal = None
                if not use_shader_normal:
                    normal = self.get_input_link(normal_socket_key)
                    if normal is None:
                        log.warn("Option use_shader_normal is disabled, but nothing is connected to '%s'" % normal_socket_key,
                                 self.node, self.material)

                elif self.node.enable_normal:
                    normal = self.get_input_link("Normal")

                if normal is not None:
                    rpr_node.set_input(rprx_input, normal)

            rpr_node = self.rpr_context.create_x_material_node(pyrprx.MATERIAL_UBER)

            # Diffuse
            if self.node.enable_diffuse:
                diffuse_weight = self.get_input_value('Diffuse Weight')
                diffuse_color = self.get_input_value('Diffuse Color')
                diffuse_roughness = self.get_input_value('Diffuse Roughness')
                backscatter_weight = self.get_input_value('Backscatter Weight')
                backscatter_color = self.get_input_value('Backscatter Color' if self.node.separate_backscatter_color else 'Diffuse Color')

                rpr_node.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, diffuse_weight)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_COLOR, diffuse_color)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS, diffuse_roughness)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, backscatter_weight)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, backscatter_color)

                set_normal('Diffuse Normal', self.node.diffuse_use_shader_normal, pyrprx.UBER_MATERIAL_DIFFUSE_NORMAL)

            else:
                # Only diffuse we have to disable manually, because it is enabled by default
                rpr_node.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, 0.0)

            # Reflection
            if self.node.enable_reflection:
                reflection_weight = self.get_input_value('Reflection Weight')
                reflection_color = self.get_input_value('Reflection Color')
                reflection_roughness = self.get_input_value('Reflection Roughness')
                reflection_anisotrophy = self.get_input_value('Reflection Anisotropy')
                reflection_anisotrophy_rotation = self.get_input_value('Reflection Anisotropy Rotation')

                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT, reflection_weight)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_COLOR, reflection_color)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ROUGHNESS, reflection_roughness)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY, reflection_anisotrophy)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY_ROTATION, reflection_anisotrophy_rotation)

                if self.node.reflection_mode == 'PBR':
                    reflection_ior = self.get_input_value('Reflection IOR')

                    rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_MODE, pyrprx.UBER_MATERIAL_REFLECTION_MODE_PBR)
                    rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_IOR, reflection_ior)

                else:
                    reflection_metalness = self.get_input_value('Reflection Metalness')

                    rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_MODE, pyrprx.UBER_MATERIAL_REFLECTION_MODE_METALNESS)
                    rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_METALNESS, reflection_metalness)

                set_normal('Reflection Normal', self.node.reflection_use_shader_normal, pyrprx.UBER_MATERIAL_REFLECTION_NORMAL)

            # Refraction
            if self.node.enable_refraction:
                refraction_weight = self.get_input_value('Refraction Weight')
                refraction_color = self.get_input_value('Refraction Color')
                refraction_roughness = self.get_input_value('Refraction Roughness')
                refraction_ior = self.get_input_value('Refraction IOR')
                refraction_absorption_distance = self.get_input_value('Refraction Absorption Distance')
                refraction_absorption_color = self.get_input_value('Refraction Absorption Color')

                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT, refraction_weight)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_COLOR, refraction_color)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_ROUGHNESS, refraction_roughness)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_IOR, refraction_ior)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_ABSORPTION_DISTANCE, refraction_absorption_distance)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_ABSORPTION_COLOR, refraction_absorption_color)

                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_THIN_SURFACE, self.node.refraction_thin_surface)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_CAUSTICS, self.node.refraction_caustics)

                set_normal('Refraction Normal', self.node.refraction_use_shader_normal, pyrprx.UBER_MATERIAL_REFRACTION_NORMAL)

            # Coating
            if self.node.enable_coating:
                coating_weight = self.get_input_value('Coating Weight')
                coating_color = self.get_input_value('Coating Color')
                coating_roughness = self.get_input_value('Coating Roughness')
                coating_thickness = self.get_input_value('Coating Thickness')
                coating_transmission_color = self.get_input_value('Coating Transmission Color')

                rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_WEIGHT, coating_weight)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_COLOR, coating_color)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_ROUGHNESS, coating_roughness)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_THICKNESS, coating_thickness)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_TRANSMISSION_COLOR, coating_transmission_color)

                coating_ior = self.get_input_value('Coating IOR')

                rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_MODE, pyrprx.UBER_MATERIAL_COATING_MODE_PBR)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_IOR, coating_ior)

                set_normal('Coating Normal', self.node.coating_use_shader_normal, pyrprx.UBER_MATERIAL_COATING_NORMAL)

            # Sheen
            if self.node.enable_sheen:
                sheen_weight = self.get_input_value('Sheen Weight')
                sheen_color = self.get_input_value('Sheen Color')
                sheen_tint = self.get_input_value('Sheen Tint')

                rpr_node.set_input(pyrprx.UBER_MATERIAL_SHEEN_WEIGHT, sheen_weight)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_SHEEN, sheen_color)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_SHEEN_TINT, sheen_tint)

            # Emission
            if self.node.enable_emission:
                emission_weight = self.get_input_value('Emission Weight')
                emission_color = self.get_input_value('Emission Color')

                rpr_node.set_input(pyrprx.UBER_MATERIAL_EMISSION_WEIGHT, emission_weight)

                emission_color = self.mul_node_value(emission_color, self.node.emission_intensity)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_EMISSION_COLOR, emission_color)

                rpr_node.set_input(pyrprx.UBER_MATERIAL_EMISSION_MODE,
                                   pyrprx.UBER_MATERIAL_EMISSION_MODE_DOUBLESIDED if self.node.emission_doublesided else
                                   pyrprx.UBER_MATERIAL_EMISSION_MODE_SINGLESIDED)

            # Subsurface
            if self.node.enable_sss:
                sss_weight = self.get_input_value('Subsurface Weight')
                sss_color = self.get_input_value('Diffuse Color' if self.node.sss_use_diffuse_color else 'Subsurface Color')
                sss_radius = self.get_input_value('Subsurface Radius')
                sss_direction = self.get_input_value('Subsurface Direction')

                rpr_node.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, sss_weight)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, (1.0, 1.0, 1.0))
                rpr_node.set_input(pyrprx.UBER_MATERIAL_SSS_WEIGHT, sss_weight)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_SSS_SCATTER_COLOR, sss_color)

                sss_radius = self.max_node_value(sss_radius, SSS_MIN_RADIUS)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_SSS_SCATTER_DISTANCE, sss_radius)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_SSS_SCATTER_DIRECTION, sss_direction)

                rpr_node.set_input(pyrprx.UBER_MATERIAL_SSS_MULTISCATTER, self.node.sss_multiscatter)

            # Transparency
            if self.node.enable_transparency:
                transparency = self.get_input_value('Transparency')

                rpr_node.set_input(pyrprx.UBER_MATERIAL_TRANSPARENCY, transparency)

            return rpr_node


class RPRShaderNodeImageTexture(RPRShaderNode):
    ''' Texture node.  Has UV input, image texture input and controls for image UV wrap and color space '''
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
        items= (
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
                return ERROR_IMAGE_COLOR

            rpr_image = image_export.sync(self.rpr_context, self.node.image)

            rpr_node = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_IMAGE_TEXTURE)

            # get image wrap type and set
            image_wrap_val = getattr(pyrpr, 'IMAGE_WRAP_TYPE_' + self.node.wrap)
            rpr_image.set_wrap(image_wrap_val)

            # set image data for node:
            rpr_node.set_input('data', rpr_image)

            uv = self.get_input_link('UV')
            if uv is not None:
                rpr_node.set_input('uv', uv)

            # apply gamma correction if needed
            if self.node.color_space == 'SRGB':
                rpr_node = self.arithmetic_node_value(rpr_node, COLOR_GAMMA, pyrpr.MATERIAL_NODE_OP_POW)

            return rpr_node


class RPRShaderNodeLookup(RPRShaderNode):
    ''' Looks up geometry values '''
    bl_label = 'RPR Lookup'

    lookup_type: bpy.props.EnumProperty(
        name='Type',
        items=(
            ('UV', "UV", "Texture coordinates"),
            ('NORMAL', "Normal", "Normal"),
            ('POS', "Position", "World position"),
            ('INVEC', "InVec", "Incident direction"),
            ('UV1', "UV1", "Second set of texture coordinates")
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
        }

        def export(self):
            rpr_node = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP)

            # RPR LookUp node types are not continuous sequence, thus the translation
            rpr_node.set_input('value', self.lookup_type_to_id[self.node.lookup_type])

            return rpr_node


class RPRShaderNodeBumpMap(RPRShaderNode):
    ''' Simple Bump map node with bump value and scale '''
    bl_label = 'RPR Bump Map'

    def init(self, context):
        self.inputs.new('rpr_socket_link', 'Map').hide_value = True
        self.inputs.new('rpr_socket_float', 'Scale').default_value = 1.0

        # adding output socket
        self.outputs.new('rpr_socket_link', "Normal")

    class Exporter(RuleNodeParser):
        nodes = {
            "Normal": {
                "type": pyrpr.MATERIAL_NODE_BUMP_MAP,
                "params": {
                    "color": "link:inputs.Map",
                    "bumpscale": "inputs.Scale",
                }
            }
        }


class RPRShaderNodeNormalMap(RPRShaderNode):
    ''' Simple Normal map node with normal value and scale
        User can also flip vector at X(up-dow) and Y(left-right) axis '''
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
            
            normal_map = self.get_input_link('Map')
            if not normal_map:
                return None

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
                normal_map = self.add_node_value(self.mul_node_value(normal_map, mul_vector),
                                                add_vector)

            rpr_node = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_NORMAL_MAP)

            rpr_node.set_input('color', normal_map)
            rpr_node.set_input('bumpscale', self.get_input_value('Scale'))

            return rpr_node


class RPRShaderNodeEmissive(RPRShaderNode):
    ''' Emissive node, only has a color and intensity '''
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
            value = self.mul_node_value(self.get_input_value('Color'), self.get_input_value('Intensity'))

            rpr_node_emissive = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_EMISSIVE)
            rpr_node_emissive.set_input("color", value)

            if self.node.emission_doublesided:
                rpr_node = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_TWOSIDED)
                rpr_node.set_input("frontface", rpr_node_emissive)
                rpr_node.set_input("backface", rpr_node_emissive)
                return rpr_node
            return rpr_node_emissive


class RPRShaderNodeBlend(RPRShaderNode):
    ''' Shader Blend node '''
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
            factor = self.get_input_value('Weight')

            if isinstance(factor, float):
                socket_key = 1 if math.isclose(factor, 0.0) else \
                    2 if math.isclose(factor, 1.0) else \
                        None
                if socket_key:
                    shader = self.get_input_link(socket_key)
                    if shader:
                        return shader
                    return self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_DIFFUSE)

            shader1 = self.get_input_link(1)
            shader2 = self.get_input_link(2)

            # like the Blender Mix Shader return default gray diffuse if no shaders connected
            if not shader1 and not shader2:
                return self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_DIFFUSE)

            rpr_node = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_BLEND)
            rpr_node.set_input('weight', self.get_input_value('Weight'))
            if shader1:
                rpr_node.set_input('color0', shader1)
            if shader2:
                rpr_node.set_input('color1', shader2)

            return rpr_node


class RPRValueNode_Math(RPRShaderNode):
    ''' RPR node for all Arithmetics operations, equivalent of Math, Vector Math, RGB Mix with some nice additions.
    Display different number of input sockets for various operations. '''
    bl_label = 'RPR Math'
    bl_width_min = 150  # for better fit of value type selector

    def change_display_type(self, context):
        """ Change inputs display type to new node display_type mode """
        for i in range(3):
            self.inputs[i].display_type = self.display_type

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
        default=False
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

            val = None

            if op == 'ADD':
                val = self.add_node_value(value1, value2)
            elif op == 'SUB':
                val = self.sub_node_value(value1, value2)
            elif op == 'MUL':
                val = self.mul_node_value(value1, value2)
            elif op == 'SIN':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_SIN)
            elif op == 'COS':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_COS)
            elif op == 'TAN':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_TAN)
            elif op == 'ASIN':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_ASIN)
            elif op == 'ACOS':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_ACOS)
            elif op == 'ATAN':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_ATAN)
            elif op == 'DOT3':
                val = self.dot3_node_value(value1, value2)
            elif op == 'DOT4':
                val = self.arithmetic_node_value(value1, value2, pyrpr.MATERIAL_NODE_OP_DOT4)
            elif op == 'CROSS3':
                val = self.arithmetic_node_value(value1, value2, pyrpr.MATERIAL_NODE_OP_CROSS3)
            elif op == 'LENGTH3':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_LENGTH3)
            elif op == 'NORMALIZE3':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_NORMALIZE3)
            elif op == 'POW':
                val = self.arithmetic_node_value(value1, value2, pyrpr.MATERIAL_NODE_OP_POW)
            elif op == 'MIN':
                val = self.min_node_value(value1, value2)
            elif op == 'MAX':
                val = self.max_node_value(value1, value2)
            elif op == 'FLOOR':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_FLOOR)
            elif op == 'MOD':
                val = self.arithmetic_node_value(value1, value2, pyrpr.MATERIAL_NODE_OP_MOD)
            elif op == 'ABS':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_ABS)
            elif op == 'SELECT_X':
                val = self.get_x_node_value(value1)
            elif op == 'SELECT_Y':
                val = self.get_y_node_value(value1)
            elif op == 'SELECT_Z':
                val = self.get_z_node_value(value1)
            elif op == 'SELECT_W':
                val = self.get_w_node_value(value1)
            elif op == 'COMBINE':
                # TODO: check if this is correct. By docs this should be (v1.x, v2.x, v1.y, v2.y), 2 arguments operation
                val = self.combine_node_value(value1, value2, value3)
            elif op == 'AVERAGE_XYZ':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_AVERAGE_XYZ)
            elif op == 'AVERAGE':
                val = self.arithmetic_node_value(value1, value2, pyrpr.MATERIAL_NODE_OP_AVERAGE)
            elif op == 'DIV':
                val = self.div_node_value(value1, value2)
            elif op == 'LOG':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_LOG)
            elif op == 'SHUFFLE_YZWX':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_SHUFFLE_YZWX)
            elif op == 'SHUFFLE_ZWXY':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_SHUFFLE_ZWXY)
            elif op == 'SHUFFLE_WXYZ':
                val = self.arithmetic_node_value(value1, None, pyrpr.MATERIAL_NODE_OP_SHUFFLE_WXYZ)
            else:
                log.warn('RPR Math : unknown operator type ({})'.format(op))
                return ERROR_IMAGE_COLOR

            if self.node.use_clamp:
                log.debug('   use_clamp: True')
                val = self.max_node_value(self.min_node_value(val, 1.0), 0.0)

            return val
