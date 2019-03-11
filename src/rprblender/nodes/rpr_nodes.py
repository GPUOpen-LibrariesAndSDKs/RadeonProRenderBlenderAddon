import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty
)
import pyrpr
import pyrprx

from .node_parser import NodeParser, RuleNodeParser


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
        self.inputs.new('NodeSocketColor', "Color").default_value = (0.8, 0.8, 0.8, 1.0)
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


    # list of parameters used for creating sockets, and changing enabled states
    # of form (name, socket_type, default_value, uber_val, enabled buttons)
    # where enabled buttons is a tuple list of buttons needed to enable
    node_sockets = {
        'Diffuse Weight': ('rpr_socket_weight_soft', 1.0, pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, 'self.enable_diffuse'),
        'Diffuse Color': ('rpr_socket_color', (0.5, 0.5, 0.5, 1.0), pyrprx.UBER_MATERIAL_DIFFUSE_COLOR, 'self.enable_diffuse'),
        'Diffuse Roughness': ('rpr_socket_weight', 0.5, pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS, 'self.enable_diffuse'),
        'Diffuse Normal': ('rpr_socket_link', None, pyrprx.UBER_MATERIAL_DIFFUSE_NORMAL, 'self.enable_diffuse and not self.diffuse_use_shader_normal'),
    
        'Backscatter Weight': ('rpr_socket_weight_soft', 1.0, pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, 'self.enable_diffuse and self.enable_backscattering'),
        'Backscatter Color': ('rpr_socket_color', (0.5, 0.5, 0.5, 1.0), pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, 'self.enable_diffuse and self.enable_backscattering'),
        
        'Reflection Weight': ('rpr_socket_weight_soft', 1.0, pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT, 'self.enable_reflection'),
        'Reflection Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), pyrprx.UBER_MATERIAL_REFLECTION_COLOR, 'self.enable_reflection'),
        'Reflection Roughness': ('rpr_socket_weight', 0.25, pyrprx.UBER_MATERIAL_REFLECTION_ROUGHNESS, 'self.enable_reflection'),
        'Reflection IOR': ('rpr_socket_ior', 1.5, pyrprx.UBER_MATERIAL_REFLECTION_IOR, "self.enable_reflection and self.reflection_mode == 'PBR'"),
        'Reflection Metalness': ('rpr_socket_weight', 0.0, pyrprx.UBER_MATERIAL_REFLECTION_METALNESS, "self.enable_reflection and self.reflection_mode == 'METALNESS'"),
        'Reflection Anisotropy': ('rpr_socket_float_min1_max1', 0.0, pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY, 'self.enable_reflection'),
        'Reflection Anisotropy Rotation': ('rpr_socket_angle360', 0.0, pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY_ROTATION, 'self.enable_reflection'),
        'Reflection Normal': ('rpr_socket_link', None, pyrprx.UBER_MATERIAL_REFLECTION_NORMAL, 'self.enable_reflection and not self.reflection_use_shader_normal'),
        
        'Refraction Weight': ('rpr_socket_weight_soft', 1.0, pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT, 'self.enable_refraction'),
        'Refraction Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), pyrprx.UBER_MATERIAL_REFRACTION_COLOR, 'self.enable_refraction'),
        'Refraction Roughness': ('rpr_socket_weight', 0.0, pyrprx.UBER_MATERIAL_REFLECTION_ROUGHNESS, 'self.enable_refraction'),
        'Refraction IOR': ('rpr_socket_ior', 1.5, pyrprx.UBER_MATERIAL_REFRACTION_IOR, 'self.enable_refraction and not self.refraction_use_reflection_ior'),
        'Refraction Absorption Distance': ('rpr_socket_float_min0_softmax10', 0.0, pyrprx.UBER_MATERIAL_REFRACTION_ABSORPTION_DISTANCE, 'self.enable_refraction'),
        'Refraction Absorption Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), pyrprx.UBER_MATERIAL_REFRACTION_ABSORPTION_COLOR, 'self.enable_refraction'),
        'Refraction Normal': ('rpr_socket_link', None, pyrprx.UBER_MATERIAL_REFRACTION_NORMAL, 'self.enable_refraction and not self.refraction_use_shader_normal'),
        
        'Coating Weight': ('rpr_socket_weight_soft', 1.0, pyrprx.UBER_MATERIAL_COATING_WEIGHT, 'self.enable_coating'),
        'Coating Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), pyrprx.UBER_MATERIAL_COATING_COLOR, 'self.enable_coating'),
        'Coating Roughness': ('rpr_socket_weight', 0.01, pyrprx.UBER_MATERIAL_COATING_ROUGHNESS, 'self.enable_coating'),
        'Coating IOR': ('rpr_socket_ior', 1.5, pyrprx.UBER_MATERIAL_COATING_IOR, 'self.enable_coating'),
        'Coating Thickness': ('rpr_socket_float_min0_softmax10', 0.0, pyrprx.UBER_MATERIAL_COATING_THICKNESS, 'self.enable_coating'),
        'Coating Transmission Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), pyrprx.UBER_MATERIAL_COATING_TRANSMISSION_COLOR, 'self.enable_coating'),
        'Coating Normal': ('rpr_socket_link', None, pyrprx.UBER_MATERIAL_COATING_NORMAL, 'self.enable_coating and not self.coating_use_shader_normal'),
    
        'Sheen Weight': ('rpr_socket_weight_soft', 1.0, pyrprx.UBER_MATERIAL_SHEEN_WEIGHT, 'self.enable_sheen'),
        'Sheen Color': ('rpr_socket_color', (0.5, 0.5, 0.5, 1.0), pyrprx.UBER_MATERIAL_SHEEN, 'self.enable_sheen'),
        'Sheen Tint': ('rpr_socket_weight', 0.5, pyrprx.UBER_MATERIAL_SHEEN_TINT, 'self.enable_sheen'),
    
        'Emission Weight': ('rpr_socket_weight_soft', 1.0, pyrprx.UBER_MATERIAL_EMISSION_WEIGHT, 'self.enable_emission'),
        'Emission Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), pyrprx.UBER_MATERIAL_EMISSION_COLOR, 'self.enable_emission'),
    
        'Subsurface Weight': ('rpr_socket_weight_soft', 1.0, pyrprx.UBER_MATERIAL_SSS_WEIGHT, 'self.enable_sss'),
        'Subsurface Color': ('rpr_socket_color', (0.436, 0.227, 0.131, 1.0), pyrprx.UBER_MATERIAL_SSS_SCATTER_COLOR, 'self.enable_sss'),
        'Subsurface Radius': ('rpr_socket_weight', 0.5, pyrprx.UBER_MATERIAL_SSS_SCATTER_DISTANCE, 'self.enable_sss'),
        'Subsurface Direction': ('rpr_socket_link', None, pyrprx.UBER_MATERIAL_SSS_SCATTER_DIRECTION, 'self.enable_sss'),
        
        'Normal': ('rpr_socket_link', None, None, 'self.enable_normal'),
        
        'Transparency': ('rpr_socket_weight', 0.0, pyrprx.UBER_MATERIAL_TRANSPARENCY, 'self.enable_transparency'),

        'Displacement': ('rpr_socket_link', None, pyrprx.UBER_MATERIAL_DISPLACEMENT, 'self.enable_displacement'),
    }

    def update_visibility(self, context):
        """ update visibility of each in list of sockets based on enabled properties """

        for socket_name, socket in self.inputs.items():
            # eval the socket enable string
            eval_string = self.node_sockets[socket_name][3]
            socket.enabled = eval(eval_string)

    enable_diffuse: BoolProperty(name="Diffuse", description="Enable Diffuse", default=True, update=update_visibility)
    diffuse_use_shader_normal: BoolProperty(name="Diffuse use shader normal", description="Use the master shader normal (disable to override)", default=True, update=update_visibility)
    enable_backscattering: BoolProperty(name="Backscattering", description="Enable Backscattering", default=False, update=update_visibility)

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
    refraction_use_reflection_ior: BoolProperty(name="Use reflection IOR", description="Use the IOR from reflection (disable to override)", default=True, update=update_visibility)
    refraction_use_shader_normal: BoolProperty(name="Refraction use shader normal", description="Use the master shader normal (disable to override)", default=True, update=update_visibility)
    refraction_thin_surface: BoolProperty(name='Refraction Thin Surface', default=False)
    refraction_caustics: BoolProperty(name='Allow Caustics', default=False)

    enable_coating: BoolProperty(name="Coating", description="Enable Coating", default=False, update=update_visibility)
    coating_use_shader_normal: BoolProperty(name="Coating use shader normal", description="Use the master shader normal (disable to override)", default=True, update=update_visibility)

    enable_sheen: BoolProperty(name="Sheen", description="Enable Sheen", default=False, update=update_visibility)

    enable_emission: BoolProperty(name="Emission", description="Enable Emission", default=False, update=update_visibility)

    enable_sss: BoolProperty(name="Subsurface", description="Enable Subsurface", default=False, update=update_visibility)
    
    enable_normal: BoolProperty(name="Normal", description="Enable Normal", default=False, update=update_visibility)   

    enable_transparency: BoolProperty(name="Transparency", description="Enable Transparency", default=False, update=update_visibility)    

    enable_displacement: BoolProperty(name="Normal", description="Enable Normal", default=False, update=update_visibility)   

    def init(self, context):
        ''' create sockets based on node_socket rules '''
        
        for socket_name, socket_desc in self.node_sockets.items():
            socket_type = socket_desc[0]
            socket_default = socket_desc[1]
            
            socket = self.inputs.new(socket_type, socket_name)
            if socket_default is not None:
                socket.default_value = socket_default

            # had value for normal types
            if socket_type == 'rpr_socket_link':
                socket.hide_value = True

        self.outputs.new('NodeSocketShader', 'Shader')

        self.update_visibility(context)


    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, 'enable_diffuse', toggle=True)
        if self.enable_diffuse:
            box = col.box()
            box.prop(self, 'diffuse_use_shader_normal')
            box.prop(self, 'enable_backscattering', toggle=True)
        
        col.prop(self, 'enable_reflection', toggle=True)
        if self.enable_reflection:
            box = col.box()
            box.prop(self, 'reflection_use_shader_normal')
            box.prop(self, 'reflection_mode', text="")

        col.prop(self, 'enable_refraction', toggle=True)
        if self.enable_refraction:
            box = col.box()
            box.prop(self, 'refraction_thin_surface')
            box.prop(self, 'refraction_use_reflection_ior')
            box.prop(self, 'refraction_caustics')
            box.prop(self, 'refraction_use_shader_normal')

        col.prop(self, 'enable_coating', toggle=True)
        if self.enable_coating:
            box = col.box()
            box.prop(self, 'coating_use_shader_normal')
        
        col.prop(self, 'enable_sheen', toggle=True)
        col.prop(self, 'enable_emission', toggle=True)
        col.prop(self, 'enable_sss', toggle=True)
        col.prop(self, 'enable_normal', toggle=True)
        col.prop(self, 'enable_transparency', toggle=True)

        # Don't enable displacements yet
        #col.prop(self, 'enable_displacement', toggle=True)


    class Exporter(NodeParser):
        def export(self):
            ''' export sockets to the uber param specced in self.node_sockets '''
            uber_node = self.rpr_context.create_x_material_node(pyrprx.MATERIAL_UBER)

            # TODO: !!! Following export code of Uber node is very simple and doesn't work correctly. This has to be fixed

            shader_normal_val = self.get_input_link('Normal')

            for socket_name, socket_desc in RPRShaderNodeUber.node_sockets.items():
                rpr_name = socket_desc[2]
                eval_string = socket_desc[3].replace("self.", "self.node.")

                # only set the param if enabled
                if not eval(eval_string):
                    continue

                if "Normal" in socket_name:
                    normal = self.get_input_link(socket_name)
                    if normal is not None:
                        uber_node.set_input(rpr_name, normal)

                    continue

                val = self.get_input_value(socket_name)
                uber_node.set_input(rpr_name, val)

            if self.node.enable_reflection:
                # set reflection mode
                uber_node.set_input(
                    pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                    pyrprx.UBER_MATERIAL_REFLECTION_MODE_METALNESS if self.node.reflection_mode == 'METALNESS' else
                    pyrprx.UBER_MATERIAL_REFLECTION_MODE_PBR
                )

            # set refraction mode and caustics
            if self.node.enable_refraction:
                uber_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_THIN_SURFACE, self.node.refraction_thin_surface)
                uber_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_CAUSTICS, self.node.refraction_caustics)

            return uber_node
