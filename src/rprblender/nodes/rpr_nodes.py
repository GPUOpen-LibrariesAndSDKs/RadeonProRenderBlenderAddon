import bpy
import json
import os

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty
)

from rprblender.utils import logging
from .node_parser import NodeParser, get_node_value, get_rpr_val


class RPRShadingNode(bpy.types.ShaderNode, NodeParser):  # , RPR_Properties):
    ''' base class for RPR shading nodes.  This is a subclass of nodeparser
        and can override the same functionality '''

    bl_compatibility = {'RPR'}
    bl_idname = 'rpr_shader_node'
    bl_label = 'RPR Shader Node'
    bl_icon = 'MATERIAL'
    bl_width_min = 300
    
    @classmethod
    def poll(cls, tree: bpy.types.NodeTree):
        return tree.bl_idname in ('ShaderNodeTree', 'RPRTreeType') and bpy.context.scene.render.engine == 'RPR'

    def __init__(self):
        pass

class RPRShadingNodeUber(RPRShadingNode):
    bl_idname = 'rpr_shader_node_uber'
    bl_label = 'RPR Uber'


    def set_from_principled(self, node:bpy.types.ShaderNodeBsdfPrincipled):
        ''' set the inputs of this from a principled node and replace the outputs
            of principled with this '''
        # TODO
        pass


    # list of parameters used for creating sockets, and changing enabled states
    # of form (name, socket_type, default_value, uber_val, enabled buttons)
    # where enabled buttons is a tuple list of buttons needed to enable
    node_sockets = {
        'Diffuse Weight': ('rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_DIFFUSE_WEIGHT', 'self.enable_diffuse'),
        'Diffuse Color': ('rpr_socket_color', (0.5, 0.5, 0.5, 1.0), 'RPRX_UBER_MATERIAL_DIFFUSE_COLOR', 'self.enable_diffuse'),
        'Diffuse Roughness': ('rpr_socket_weight', 0.5, 'RPRX_UBER_MATERIAL_DIFFUSE_ROUGHNESS', 'self.enable_diffuse'),
        'Diffuse Normal': ('rpr_socket_link', None, 'RPRX_UBER_MATERIAL_DIFFUSE_NORMAL', 'self.enable_diffuse and not self.diffuse_use_shader_normal'),
    
        'Backscatter Weight': ('rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_BACKSCATTER_WEIGHT', 'self.enable_diffuse and self.enable_backscattering'),
        'Backscatter Color': ('rpr_socket_color', (0.5, 0.5, 0.5, 1.0), 'RPRX_UBER_MATERIAL_BACKSCATTER_COLOR', 'self.enable_diffuse and self.enable_backscattering'),
        
        'Reflection Weight': ('rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_REFLECTION_WEIGHT', 'self.enable_reflection'),
        'Reflection Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), 'RPRX_UBER_MATERIAL_REFLECTION_COLOR', 'self.enable_reflection'),
        'Reflection Roughness': ('rpr_socket_weight', 0.25, 'RPRX_UBER_MATERIAL_REFLECTION_ROUGHNESS', 'self.enable_reflection'),
        'Reflection IOR': ('rpr_socket_ior', 1.5, 'RPRX_UBER_MATERIAL_REFLECTION_IOR', "self.enable_reflection and self.reflection_mode == 'RPRX_UBER_MATERIAL_REFLECTION_MODE_PBR'"),
        'Reflection Metalness': ('rpr_socket_weight', 0.0, 'RPRX_UBER_MATERIAL_REFLECTION_METALNESS', "self.enable_reflection and self.reflection_mode == 'RPRX_UBER_MATERIAL_REFLECTION_MODE_METALNESS'"),
        'Reflection Anisotropy': ('rpr_socket_float_min1_max1', 0.0, 'RPRX_UBER_MATERIAL_REFLECTION_ANISOTROPY', 'self.enable_reflection'),
        'Reflection Anisotropy Rotation': ('rpr_socket_angle360', 0.0, 'RPRX_UBER_MATERIAL_REFLECTION_ANISOTROPY_ROTATION', 'self.enable_reflection'),
        'Reflection Normal': ('rpr_socket_link', None, 'RPRX_UBER_MATERIAL_REFLECTION_NORMAL', 'self.enable_reflection and not self.reflection_use_shader_normal'),
        
        'Refraction Weight': ('rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_REFRACTION_WEIGHT', 'self.enable_refraction'),
        'Refraction Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), 'RPRX_UBER_MATERIAL_REFRACTION_COLOR', 'self.enable_refraction'),
        'Refraction Roughness': ('rpr_socket_weight', 0.0, 'RPRX_UBER_MATERIAL_REFLECTION_ROUGHNESS', 'self.enable_refraction'),
        'Refraction IOR': ('rpr_socket_ior', 1.5, 'RPRX_UBER_MATERIAL_REFRACTION_IOR', 'self.enable_refraction and not self.refraction_use_reflection_ior'),
        'Refraction Absorption Distance': ('rpr_socket_float_min0_softmax10', 0.0, 'RPRX_UBER_MATERIAL_REFRACTION_ABSORPTION_DISTANCE', 'self.enable_refraction'),
        'Refraction Absorption Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), 'RPRX_UBER_MATERIAL_REFRACTION_ABSORPTION_COLOR', 'self.enable_refraction'),
        'Refraction Normal': ('rpr_socket_link', None, 'RPRX_UBER_MATERIAL_REFRACTION_NORMAL', 'self.enable_refraction and not self.refraction_use_shader_normal'),
        
        'Coating Weight': ('rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_COATING_WEIGHT', 'self.enable_coating'),
        'Coating Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), 'RPRX_UBER_MATERIAL_COATING_COLOR', 'self.enable_coating'),
        'Coating Roughness': ('rpr_socket_weight', 0.01, 'RPRX_UBER_MATERIAL_COATING_ROUGHNESS', 'self.enable_coating'),
        'Coating IOR': ('rpr_socket_ior', 1.5, 'RPRX_UBER_MATERIAL_COATING_IOR', 'self.enable_coating'),
        'Coating Thickness': ('rpr_socket_float_min0_softmax10', 0.0, 'RPRX_UBER_MATERIAL_COATING_THICKNESS', 'self.enable_coating'),
        'Coating Transmission Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), 'RPRX_UBER_MATERIAL_COATING_TRANSMISSION_COLOR', 'self.enable_coating'),
        'Coating Normal': ('rpr_socket_link', None, 'RPRX_UBER_MATERIAL_COATING_NORMAL', 'self.enable_coating and not self.coating_use_shader_normal'),
    
        'Sheen Weight': ('rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_SHEEN_WEIGHT', 'self.enable_sheen'),
        'Sheen Color': ('rpr_socket_color', (0.5, 0.5, 0.5, 1.0), 'RPRX_UBER_MATERIAL_SHEEN', 'self.enable_sheen'),
        'Sheen Tint': ('rpr_socket_weight', 0.5, 'RPRX_UBER_MATERIAL_SHEEN_TINT', 'self.enable_sheen'),
    
        'Emission Weight': ('rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_EMISSION_WEIGHT', 'self.enable_emission'),
        'Emission Color': ('rpr_socket_color', (1.0, 1.0, 1.0, 1.0), 'RPRX_UBER_MATERIAL_EMISSION_COLOR', 'self.enable_emission'),
    
        'Subsurface Weight': ('rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_SSS_WEIGHT', 'self.enable_sss'),
        'Subsurface Color': ('rpr_socket_color', (0.436, 0.227, 0.131, 1.0), 'RPRX_UBER_MATERIAL_SSS_SCATTER_COLOR', 'self.enable_sss'),
        'Subsurface Radius': ('rpr_socket_weight', 0.5, 'RPRX_UBER_MATERIAL_SSS_SCATTER_DISTANCE', 'self.enable_sss'),
        'Subsurface Direction': ('rpr_socket_link', None, 'RPRX_UBER_MATERIAL_SSS_SCATTER_DIRECTION', 'self.enable_sss'),
        
        'Normal': ('rpr_socket_link', None, None, 'self.enable_normal'),
        
        'Transparency': ('rpr_socket_weight', 0.0, 'RPRX_UBER_MATERIAL_TRANSPARENCY', 'self.enable_transparency'),

        'Displacement': ('rpr_socket_link', None, 'RPRX_UBER_MATERIAL_DISPLACEMENT', 'self.enable_displacement'),
    
    }

    def update_visibility(self, context):
        ''' update visibility of each in list of sockets based on enabled properties '''
        for socket_name, socket in self.inputs.items():
            socket_type, socket_default, rpr_name, eval_string = self.node_sockets[socket_name]

            # eval the socket enable string
            socket.enabled = eval(eval_string)
    

    enable_diffuse: BoolProperty(name="Diffuse", description="Enable Diffuse", default=True, update=update_visibility)
    diffuse_use_shader_normal: BoolProperty(name="Diffuse use shader normal", description="Use the master shader normal (disable to override)", default=True, update=update_visibility)
    enable_backscattering: BoolProperty(name="Backscattering", description="Enable Backscattering", default=False, update=update_visibility)

    enable_reflection: BoolProperty(name="Reflection", description="Enable Reflection", default=True, update=update_visibility)
    reflection_use_shader_normal: BoolProperty(name="Reflection use shader normal", description="Use the master shader normal (disable to override)", default=True, update=update_visibility)
    reflection_mode: EnumProperty(name="Reflection Mode", description="Set reflection via metalness or IOR", default='RPRX_UBER_MATERIAL_REFLECTION_MODE_METALNESS', update=update_visibility,
                                  items=(('RPRX_UBER_MATERIAL_REFLECTION_MODE_METALNESS', 'Metalness', ''), ('RPRX_UBER_MATERIAL_REFLECTION_MODE_PBR', 'IOR', '')))


    enable_refraction: BoolProperty(name="Refraction", description="Enable Refraction", default=False, update=update_visibility)
    refraction_use_reflection_ior: BoolProperty(name="Use reflection IOR", description="Use the IOR from reflection (disable to override)", default=True, update=update_visibility)
    refraction_use_shader_normal: BoolProperty(name="Refraction use shader normal", description="Use the master shader normal (disable to override)", default=True, update=update_visibility)

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
            socket_type, socket_default, rpr_name, eval_string = socket_desc
            
            socket = self.inputs.new(socket_type, socket_name)
            if socket_default is not None:
                socket.default_value = socket_default

            # had value for normal types
            if socket_type == 'rpr_socket_link':
                socket.hide_value

        self.outputs.new('rpr_socket_link', 'Shader')

        self.update_visibility(None)
        # save self as blender_node
        self.blender_node = self


    def export(self, socket, material_exporter):
        ''' export sockets to the uber param specced in self.node_sockets '''
        self.material_exporter = material_exporter
        uber_node = material_exporter.create_rpr_node('RPRX_MATERIAL_UBER', material_exporter.get_node_key(self, 'Shader'))

        shader_normal_val = get_node_value(material_exporter, self, 'Normal') if self.inputs['Normal'].is_linked else None

        for socket_name, socket_desc in self.node_sockets.items():
            socket_type, socket_default, rpr_name, eval_string = socket_desc

            # only set the param if enabled
            if rpr_name and eval(eval_string):
                val = get_node_value(material_exporter, self, socket_name)
                if val is not None:
                    # if this normal and is unlinked skip
                    if 'Normal' in socket_name and not self.inputs[socket_name].is_linked:
                        continue
                    else:
                        uber_node.set_input(get_rpr_val(rpr_name), val)


            # if normal is not enabled, set to the shader normal
            elif rpr_name and 'Normal' in socket_name and shader_normal_val:
                uber_node.set_input(get_rpr_val(rpr_name), shader_normal_val)
            
            else:
                # if this is a weight and not enabled, set to 0
                if "Weight" in socket_name:
                    uber_node.set_input(get_rpr_val(rpr_name), 0.0)

        # set reflection mode
        uber_node.set_input(get_rpr_val('RPRX_UBER_MATERIAL_REFLECTION_MODE'), get_rpr_val(self.reflection_mode))
        
        return uber_node


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
            box.prop(self, 'reflection_mode')

        col.prop(self, 'enable_coating', toggle=True)
        if self.enable_reflection:
            box = col.box()
            box.prop(self, 'coating_use_shader_normal')
        
        col.prop(self, 'enable_sheen', toggle=True)
        col.prop(self, 'enable_emission', toggle=True)
        col.prop(self, 'enable_sss', toggle=True)
        col.prop(self, 'enable_normal', toggle=True)
        col.prop(self, 'enable_transparency', toggle=True)
        # Don't enable displacements yet
        #col.prop(self, 'enable_displacement', toggle=True)

            