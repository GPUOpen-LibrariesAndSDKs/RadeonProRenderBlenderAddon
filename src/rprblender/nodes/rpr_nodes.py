import bpy
import json
import os

import bpy

from rprblender.utils import logging
from .node_parser import NodeParser, get_node_value

class RPRShadingNode(bpy.types.ShaderNode, NodeParser):  # , RPR_Properties):
    ''' base class for RPR shading nodes.  This is a subclass of nodeparser
        and can override the same functionality '''

    bl_compatibility = {'RPR'}
    bl_idname = 'rpr_shader_node'
    bl_label = 'RPR Shader Node'
    bl_icon = 'MATERIAL'

    
    @classmethod
    def poll(cls, tree: bpy.types.NodeTree):
        return tree.bl_idname in ('ShaderNodeTree', 'RPRTreeType') and bpy.context.scene.render.engine == 'RPR'



class RPRShadingNodeUber(RPRShadingNode):
    bl_idname = 'rpr_shader_node_uber'
    bl_label = 'RPR Uber'


    def set_from_principled(self, node:bpy.types.ShaderNodeBsdfPrincipled):
        ''' set the inputs of this from a principled node and replace the outputs
            of principled with this '''
        # TODO
        pass


    # list of parameters used for creating sockets, and changing enabled states
    # of form (name, socket_type, default_value, uber_val)
    node_sockets = {
        "diffuse": [
            ('Diffuse Color', 'rpr_socket_color', (0.5, 0.5, 0.5, 1.0), 'RPRX_UBER_MATERIAL_DIFFUSE_COLOR'),
            ('Diffuse Weight', 'rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_DIFFUSE_WEIGHT'),
            ('Diffuse Roughness', 'rpr_socket_weight', 0.5, 'RPRX_UBER_MATERIAL_DIFFUSE_ROUGHNESS'),
            ('Diffuse Normal', 'rpr_socket_link', None, 'RPRX_UBER_MATERIAL_DIFFUSE_NORMAL'),
        ],
        "backscatter": [
            ('Backscatter Color', 'rpr_socket_color', (0.5, 0.5, 0.5, 1.0), 'RPRX_UBER_MATERIAL_BACKSCATTER_COLOR'),
            ('Diffuse Weight', 'rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_BACKSCATTER_WEIGHT'),
        ],
        "reflection": [
            ('Reflection Color', 'rpr_socket_color', (1.0, 1.0, 1.0, 1.0), 'RPRX_UBER_MATERIAL_REFLECTION_COLOR'),
            ('Reflection Weight', 'rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_REFLECTION_WEIGHT'),
            ('Reflection Roughness', 'rpr_socket_weight', 0.25, 'RPRX_UBER_MATERIAL_REFLECTION_ROUGHNESS'),
            ('Reflection Anisotropy', 'rpr_socket_float_min1_max1', 0.0, 'RPRX_UBER_MATERIAL_REFLECTION_ANISOTROPY'),
            ('Reflection Anisotropy Rotation', 'rpr_socket_angle360', 0.0, 'RPRX_UBER_MATERIAL_REFLECTION_ANISOTROPY_ROTATION'),
            ('Reflection IOR', 'rpr_socket_ior', 1.5, 'RPRX_UBER_MATERIAL_REFLECTION_IOR'),
            ('Reflection METALNESS', 'rpr_socket_weight', 0.0, 'RPRX_UBER_MATERIAL_REFLECTION_METALNESS'),
            ('Reflection Normal', 'rpr_socket_link', None, 'RPRX_UBER_MATERIAL_REFLECTION_NORMAL'),
        ],
        "refraction": [
            ('Refraction Color', 'rpr_socket_color', (1.0, 1.0, 1.0, 1.0), 'RPRX_UBER_MATERIAL_REFRACTION_COLOR'),
            ('Refraction Weight', 'rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_REFRACTION_WEIGHT'),
            ('Refraction Roughness', 'rpr_socket_weight', 0.0, 'RPRX_UBER_MATERIAL_REFLECTION_ROUGHNESS'),
            ('Refraction IOR', 'rpr_socket_ior', 1.5, 'RPRX_UBER_MATERIAL_REFRACTION_IOR'),
            ('Refraction Absorption Distance', 'rpr_socket_float_min0_softmax10', 0.0, 'RPRX_UBER_MATERIAL_REFRACTION_DISTANCE'),
            ('Refraction Absorption Color', 'rpr_socket_color', (1.0, 1.0, 1.0, 1.0), 'RPRX_UBER_MATERIAL_REFRACTION_ABSORPTION_COLOR'),
            ('Refraction Normal', 'rpr_socket_link', None, 'RPRX_UBER_MATERIAL_REFRACTION_NORMAL'),
        ],
        "coating": [
            ('Coating Color', 'rpr_socket_color', (1.0, 1.0, 1.0, 1.0), 'RPRX_UBER_MATERIAL_COATING_COLOR'),
            ('Coating Weight', 'rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_COATING_WEIGHT'),
            ('Coating Roughness', 'rpr_socket_weight', 0.01, 'RPRX_UBER_MATERIAL_COATING_ROUGHNESS'),
            ('Coating IOR', 'rpr_socket_ior', 1.5, 'RPRX_UBER_MATERIAL_COATING_IOR'),
            ('Coating Thickness', 'rpr_socket_float_min0_softmax10', 0.0, 'RPRX_UBER_MATERIAL_COATING_THICKNESS'),
            ('Coating Transmission Color', 'rpr_socket_color', (1.0, 1.0, 1.0, 1.0), 'RPRX_UBER_MATERIAL_COATING_TRANSMISSION_COLOR'),
            ('Coating Normal', 'rpr_socket_link', None, 'RPRX_UBER_MATERIAL_COATING_NORMAL'),
        ],
        "sheen": [
            ('Sheen Color', 'rpr_socket_color', (0.5, 0.5, 0.5, 1.0), 'RPRX_UBER_MATERIAL_SHEEN_COLOR'),
            ('Sheen Weight', 'rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_SHEEN_WEIGHT'),
            ('Sheen Tint', 'rpr_socket_weight', 0.5, 'RPRX_UBER_MATERIAL_SHEEN_TINT'),
        ],
        "emissive": [
            ('Emissive Color', 'rpr_socket_color', (1.0, 1.0, 1.0, 1.0), 'RPRX_UBER_MATERIAL_EMISSIVE_COLOR'),
            ('Emissive Weight', 'rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_EMISSIVE_WEIGHT'),
        ],
        "subsurface": [
            ('Subsurface Color', 'rpr_socket_color', (0.436, 0.227, 0.131, 1.0), 'RPRX_UBER_MATERIAL_SSS_SCATTER_COLOR'),
            ('Subsurface Weight', 'rpr_socket_weight_soft', 1.0, 'RPRX_UBER_MATERIAL_SSS_WEIGHT'),
            ('Subsurface Radius', 'rpr_socket_weight', 0.5, 'RPRX_UBER_MATERIAL_SSS_SCATTER_DISTANCE'),
            ('Subsurface Direction', 'rpr_socket_link', None, 'RPRX_UBER_MATERIAL_SSS_SCATTER_DIRECTION'),
        ],
        "normal": [
            ('Normal', 'rpr_socket_link', None, None),
        ],
        "transparency": [
            ('Transparency', 'rpr_socket_weight', 0.0, 'RPRX_UBER_MATERIAL_TRANSPARENCY'),
        ],
        "displacement": [
            ('Displacement', 'rpr_socket_link', None, 'RPRX_UBER_MATERIAL_DISPLACEMENT'),
        ],

    }


    diffuse_enabled: BoolProperty(
        name="Diffuse",
        description="Enable Diffuse",
        default=True
    )

    diffuse_enabled: BoolProperty(
        name="Diffuse",
        description="Enable Diffuse",
        default=True
    )

    reflection_enabled: BoolProperty(
        name="Diffuse",
        description="Enable Diffuse",
        default=True
    )

    def update_visibility(self, context):
        ''' update visibility of list of sockets based on enabled properties '''
        for lobe_name, sockets in self.node_sockets.items():
            lobe_enabled = getattr(self, lobe_name + '_enabled')
            for socket_name, socket_type, default, rpr_val in sockets:
                self.inputs[socket_name].enabled = lobe_enabled

    def __init__(self, context):
        ''' create sockets based on node_socket rules '''
        for lobe, sockets in self.node_sockets.items():
            for socket_name, socket_type, default_val, rpr_val in sockets:
                socket = self.inputs.new(socket_type, socket_name)
                if default_val is not None:
                    socket.default_value = default_val

                # had value for normal types
                if socket_type == 'rpr_socket_link':
                    spcket.hide_value

        self.update_visibility(None)
        # save self as blender_node
        self.blender_node = self

    def export(self, socket, material_exporter):
        ''' export based on rules '''
        # todo handle special cases. 
        self.material_exporter = material_exporter
        uber_node = material_exporter.create_rpr_node('RPRX_MATERIAL_UBER')

        for lobe_name, sockets in self.node_sockets.items():
            lobe_enabled = getattr(self, lobe_name + '_enabled')
            
            if lobe_enable:
                for socket_name, socket_type, default, rpr_val in sockets:
                    val = get_node_value(material_exporter, self, socket.name)
                    if val is not None:
                        uber_node.set_input(get_rpr_val(rpr_val), val)

            else:
                # find the weight, set to 0
                for socket_name, socket_type, default, rpr_val in sockets:
                    if "Weight" in socket_name:
                        uber_node.set_input(get_rpr_val(rpr_val), 0.0)
                        break

        return uber_node
