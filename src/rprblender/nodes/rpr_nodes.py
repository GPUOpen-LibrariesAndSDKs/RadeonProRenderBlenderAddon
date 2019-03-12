import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
)
import pyrpr
import pyrprx

from .node_parser import NodeParser, RuleNodeParser
from .blender_nodes import SSS_MIN_RADIUS

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
        'Coating IOR': ('rpr_socket_ior', 1.5, "self.enable_coating and self.coating_mode == 'PBR'"),
        'Coating Metalness': ('rpr_socket_weight', 0.0, "self.enable_coating and self.coating_mode == 'METALNESS'"),
        'Coating Thickness': ('rpr_socket_float_min0_softmax10', 0.0, "self.enable_coating"),
        'Coating Transmission Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), "self.enable_coating"),
        'Coating Normal': ('NodeSocketVector', None, "self.enable_coating and not self.coating_use_shader_normal"),
    
        'Sheen Weight': ('rpr_socket_weight_soft', 1.0, "self.enable_sheen"),
        'Sheen Color': ('rpr_socket_color', (0.5, 0.5, 0.5, 1.0), "self.enable_sheen"),
        'Sheen Tint': ('rpr_socket_weight', 0.5, "self.enable_sheen"),
    
        'Emission Weight': ('rpr_socket_weight_soft', 1.0, "self.enable_emission"),
        'Emission Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), "self.enable_emission"),
    
        'Subsurface Weight': ('rpr_socket_weight_soft', 1.0, "self.enable_sss"),
        'Subsurface Color': ('rpr_socket_color', (0.436, 0.227, 0.131, 1.0), "self.enable_sss and self.sss_use_diffuse_color"),
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
    coating_mode: EnumProperty(
        name="Coating Mode",
        description="Set coating via metalness or IOR",
        items=(('METALNESS', "Metalness", ""),
               ('PBR', "IOR", "")),
        default='METALNESS',
        update=update_visibility
    )

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
            c.prop(self, 'coating_mode', text="")
        
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

                if self.node.coating_mode == 'PBR':
                    coating_ior = self.get_input_value('Coating IOR')

                    rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_MODE, pyrprx.UBER_MATERIAL_COATING_MODE_PBR)
                    rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_IOR, coating_ior)

                else:
                    coating_metalness = self.get_input_value('Coating Metalness')

                    rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_MODE, pyrprx.UBER_MATERIAL_COATING_MODE_METALNESS)
                    rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_METALNESS, coating_metalness)

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
