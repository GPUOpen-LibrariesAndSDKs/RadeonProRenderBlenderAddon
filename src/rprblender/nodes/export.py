import math
import numpy as np

import bpy
import pyrpr
import pyrprx

from . import MaterialError
from .export_by_rules import create_rpr_node_by_rules, rulesets
from rprblender.utils.material import find_output_node_in_tree
from rprblender import utils
from rprblender.utils import image as image_utils
from rprblender.utils import light as light_utils

from rprblender.utils import logging
log = logging.Log(tag='material', level='debug')


ERROR_COLOR = (1.0, 0.0, 1.0, 1.0)


# SUPPORT METHODS

def get_fake_material(rpr_context) -> pyrpr.MaterialNode:
    key = 'FAKE_MATERIAL'

    rpr_mat = rpr_context.materials.get(key, None)
    if rpr_mat:
        return rpr_mat

    rpr_mat = rpr_context.create_material_node('FAKE_MATERIAL_NODE', pyrpr.MATERIAL_NODE_PASSTHROUGH)
    rpr_mat.set_input('color', ERROR_COLOR)
    rpr_context.set_material_node_as_material(key, rpr_mat)

    return rpr_mat


def get_node_socket(node, name=None, index=None):
    if name:
        socket = node.inputs.get(name, None)
        if socket is None:
            return None
    elif index:
        if index < len(node.inputs):
            socket = node.inputs[index]
        else:
            return None
    else:
        return None

    log("get_node_socket({}, {}, {}): {}; linked {}".
        format(node, name, index, socket,
               "{}; links number {}".format(socket.is_linked, len(socket.links)) if socket.is_linked else "False"))

    if socket.is_linked:
        if socket.links[0].is_valid:
            return socket.links[0].from_socket

        log.error("Invalid link found: <{}>.{} to <{}>.{}".
                  format(socket.links[0].from_node.name, socket.links[0].from_socket.name,
                         socket.links[0].to_node.name, socket.links[0].to_socket.name))
    return None


class MaterialExporter:

    def __init__(self, rpr_context, material: bpy.types.Material):
        self.rpr_context = rpr_context
        self.material = material

    def export(self):
        """Entry method to export material if shader nodes tree present"""
        mat_key = utils.key(self.material)

        rpr_material = self.rpr_context.materials.get(mat_key, None)
        if rpr_material:
            return rpr_material

        tree = getattr(self.material, 'node_tree', None)
        if not tree:
            log.warn("Empty material tree, skipping", self.material)
            return None

        log("export", self.material, tree)
        try:
            # looking for output node
            output_node = find_output_node_in_tree(tree)
            if not output_node:
                raise MaterialError("No valid output node found", self.material)

            rpr_material = self.parse_output_node(output_node)
            if rpr_material:
                self.rpr_context.set_material_node_as_material(mat_key, rpr_material)

            return rpr_material

        except MaterialError as e:
            log.error(e, "Fake material would be created")
            return get_fake_material(self.rpr_context)

    def node_key(self, node, socket=None):
        if socket:
            return (utils.key(self.material), node.name, socket.name)

        return (utils.key(self.material), node.name)

    def get_node_output_default_value(self, node):
        val = node.outputs[0].default_value
        if isinstance(val, (int, float)):
            return float(val)

        if len(val) in (3, 4):
            return tuple(val)

        raise TypeError("Incorrect node default value", self.material, node, val)

    def get_socket_link(self, node, socket_key):
        socket = node.inputs[socket_key]

        if socket.is_linked:
            link = socket.links[0]
            if link.is_valid:
                return self.parse_node(link.from_node, link.from_socket)

            log.error(
                "Invalid link found: <{}>.{} to <{}>.{}".format(
                    link.from_node.name, link.from_socket.name,
                    link.to_node.name, link.to_socket.name
                ),
                self.material
            )

        return None

    def get_socket_default(self, node, socket_key):
        socket = node.inputs[socket_key]

        val = socket.default_value
        if isinstance(val, (int, float)):
            return float(val)

        if len(val) in (3, 4):
            return tuple(val)

        raise TypeError("Incorrect socket default value", self.material, socket, val)

    def get_socket_value(self, node, socket_key):
        val = self.get_socket_link(node, socket_key)
        if val is not None:
            return val

        return self.get_socket_default(node, socket_key)

    #####
    # Nodes parsing methods

    def parse_output_node(self, node):
        surface_socket = get_node_socket(node, name='Surface')  # 'Surface'
        if not surface_socket:
            raise MaterialError("No input for Surface socket", self.material, node)

        log("parse_output_node", self.material, node, surface_socket, surface_socket.node)

        rpr_node = self.parse_node(surface_socket.node, surface_socket)

        # TODO: Parse other sockets: volume and displacement

        return rpr_node

    def parse_node(self, node, socket):
        node_parsers = {
            # shaders
            'ShaderNodeBsdfPrincipled': self.parse_node_principled,
            'ShaderNodeBsdfDiffuse': self.parse_node_diffuse,
            'ShaderNodeEmission': self.parse_node_emission,
            'ShaderNodeBsdfTransparent': self.parse_node_transparent,
            'ShaderNodeMixShader': self.parse_node_mix,
            'ShaderNodeBsdfGlossy': self.parse_node_glossy,

            # inputs
            'ShaderNodeTexImage': self.parse_node_image_texture,
            'ShaderNodeRGB': self.get_node_output_default_value,
            'ShaderNodeValue': self.get_node_output_default_value,
            'ShaderNodeBlackbody': self.parse_node_blackbody,

            # color
            'ShaderNodeInvert': self.parse_node_invert,
            'ShaderNodeBrightContrast': self.parse_node_bright_contrast,

            # bumps
            'ShaderNodeBump': self.parse_node_bump,
            'ShaderNodeNormalMap': self.parse_node_normal_map,
        }
        node_socket_parsers = {
            'ShaderNodeLightPath': self.parse_node_light_path,
            'ShaderNodeLightFalloff': self.parse_node_light_falloff,
            'ShaderNodeTexChecker': self.parse_node_tex_checker,
        }

        rpr_node = self.rpr_context.material_nodes.get(self.node_key(node), None)
        if rpr_node:
            return rpr_node

        rpr_node = self.rpr_context.material_nodes.get(self.node_key(node, socket), None)
        if rpr_node:
            return rpr_node

        # TODO: discuss about using rules to parse nodes
        # Can we export node using rules?
        rules = rulesets.get(node.bl_idname, None)
        if rules:
            return self.create_node_by_rules(node, rules, socket)

        if node.bl_idname in node_parsers:
            return node_parsers[node.bl_idname](node)

        if node.bl_idname in node_socket_parsers:
            return node_socket_parsers[node.bl_idname](node, socket)

        log.warn("Ignoring unsupported node", self.material, node, socket)
        return None

    def create_node_by_rules(self, blender_node, rules, socket):
        node_key = self.node_key(blender_node, socket)

        log("Parsing node '{}' by rules using output socket '{}'".format(blender_node, socket.name))
        # get all input values and parse linked nodes
        input_values = {}
        for entry in blender_node.inputs.values():
            log.debug("[{}] input '{}'/'{}': {}".format(blender_node.name, entry.name, entry.type, entry.default_value))
        for key, entry in rules['inputs'].items():
            input_values[key] = self.get_socket_value(blender_node, entry['label'])

        # all rules error check should be done at JSON loading time
        output_socket_info = rules['outputs'][socket.name]
        subnode_name = output_socket_info["node"]

        node = create_rpr_node_by_rules(self.rpr_context, node_key, subnode_name, input_values, rules['nodes'])

        return node

    #####
    # Nodes by methods

    def parse_node_diffuse(self, blender_node):
        color = self.get_socket_value(blender_node, 'Color')
        roughness = self.get_socket_value(blender_node, 'Roughness')

        rpr_node = self.rpr_context.create_material_node(self.node_key(blender_node), pyrpr.MATERIAL_NODE_DIFFUSE)
        rpr_node.set_input('color', color)
        rpr_node.set_input('roughness', roughness)

        return rpr_node

    def parse_node_emission(self, blender_node):
        color = self.get_socket_value(blender_node, 'Color')
        strength = self.get_socket_value(blender_node, 'Strength')

        rpr_node = self.rpr_context.create_material_node(self.node_key(blender_node), pyrpr.MATERIAL_NODE_EMISSIVE)
        rpr_node.set_input('color', self.rpr_context.mul_node_value(color, strength))

        return rpr_node

    def parse_node_transparent(self, blender_node):
        color = self.get_socket_value(blender_node, 'Color')

        rpr_node = self.rpr_context.create_material_node(self.node_key(blender_node), pyrpr.MATERIAL_NODE_TRANSPARENT)
        rpr_node.set_input('color', color)

        return rpr_node

    def parse_node_glossy(self, blender_node):
        color = self.get_socket_value(blender_node, 'Color')
        normal = self.get_socket_link(blender_node, 'Normal')

        # TODO: Looks like Uber should be here
        rpr_node = self.rpr_context.create_material_node(self.node_key(blender_node), pyrpr.MATERIAL_NODE_REFLECTION)
        rpr_node.set_input('color', color)
        if normal is not None:
            rpr_node.set_input('normal', normal)

        return rpr_node

    def parse_node_image_texture(self, blender_node):
        image_object = blender_node.image
        if not image_object:
            return None

        try:
            rpr_image = image_utils.get_rpr_image(self.rpr_context, image_object)
        except ValueError as e:  # texture loading error, return "Texture Error/Absence" image
            log.error("Image error: {}".format(e))
            return ERROR_COLOR

        rpr_node = self.rpr_context.create_material_node(self.node_key(blender_node), pyrpr.MATERIAL_NODE_IMAGE_TEXTURE)
        rpr_node.set_input('data', rpr_image)

        # TODO parse "Vector" UV mapping input socket
        # rpr_node.set_input('uv', None)
        return rpr_node

    def parse_node_principled(self, blender_node) -> pyrprx.Material:
        def enabled(val):
            if val is None:
                return False

            if isinstance(val, float) and math.isclose(val, 0.0):
                return False

            return True

        base_color = self.get_socket_value(blender_node, 'Base Color')
        roughness = self.get_socket_value(blender_node, 'Roughness')
        subsurface = self.get_socket_value(blender_node, 'Subsurface')
        subsurface_radius = self.get_socket_value(blender_node, 'Subsurface Radius')
        subsurface_color = self.get_socket_value(blender_node, 'Subsurface Color')
        metalness = self.get_socket_value(blender_node, 'Metallic')
        specular = self.get_socket_value(blender_node, 'Specular')
        specular_tint = self.get_socket_value(blender_node, 'Specular Tint')
        anisotropic = self.get_socket_value(blender_node, 'Anisotropic')
        anisotropic_rotation = self.get_socket_value(blender_node, 'Anisotropic Rotation')
        clearcoat = self.get_socket_value(blender_node, 'Clearcoat')
        clearcoat_roughness = self.get_socket_value(blender_node, 'Clearcoat Roughness')
        sheen = self.get_socket_value(blender_node, 'Sheen')
        sheen_tint = self.get_socket_value(blender_node, 'Sheen Tint')
        transmission = self.get_socket_value(blender_node, 'Transmission')
        ior = self.get_socket_value(blender_node, 'IOR')
        transmission_roughness = self.get_socket_value(blender_node, 'Transmission Roughness')
        normal_map = self.get_socket_link(blender_node, 'Normal')
        clearcoat_normal_map = self.get_socket_link(blender_node, 'Clearcoat Normal')
        tangent = self.get_socket_link(blender_node, 'Tangent')

        rpr_node = self.rpr_context.create_x_material_node(self.node_key(blender_node), pyrprx.MATERIAL_UBER)

        # Glass need PBR reflection type and disabled diffuse channel
        is_not_glass = enabled(metalness) or not enabled(transmission)

        # Base color -> Diffuse (always on, except for glass)
        if is_not_glass:
            rpr_node.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_COLOR, base_color)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, 1.0)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS, roughness)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, 0.0)
        else:
            # TODO replace with mix of diffuse/refractive shaders with transmission as a mask/factor
            # TODO also adjust to core changes
            rpr_node.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, 0.0)

        # Metallic -> Reflection (always on unless specular is set to non-physical 0.0)
        if enabled(specular):
            # Cycles default value of 0.5 is equal to RPR weight of 1.0
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT, self.rpr_context.mul_node_value(specular, 2.0))

            # mode 'metal' unless transmission is set and metallic is 0
            if is_not_glass:
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                                        pyrprx.UBER_MATERIAL_REFLECTION_MODE_METALNESS)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_METALNESS, metalness)
            else:
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                                        pyrprx.UBER_MATERIAL_REFLECTION_MODE_PBR)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_IOR, ior)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_COLOR, base_color)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ROUGHNESS, roughness)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY, anisotropic)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY_ROTATION, anisotropic_rotation)

        # Clearcloat
        if enabled(clearcoat):
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_COLOR, (1.0, 1.0, 1.0, 1.0))
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_WEIGHT, clearcoat)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_ROUGHNESS, clearcoat_roughness)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_THICKNESS, 0.0)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_TRANSMISSION_COLOR, (0.0, 0.0, 0.0, 0.0))
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_MODE,
                                    pyrprx.UBER_MATERIAL_COATING_MODE_PBR)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_IOR, ior)

        # Sheen
        if enabled(sheen):
            rpr_node.set_input(pyrprx.UBER_MATERIAL_SHEEN_WEIGHT, sheen)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_SHEEN, base_color)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_SHEEN_TINT, sheen_tint)

        # No Emission for Cycles Principled BSDF
        rpr_node.set_input(pyrprx.UBER_MATERIAL_EMISSION_WEIGHT, 0.0)

        # Subsurface
        if enabled(subsurface):
            rpr_node.set_input(pyrprx.UBER_MATERIAL_SSS_WEIGHT, subsurface)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_SSS_SCATTER_COLOR, subsurface_color)

            # check for 0 channel value(for Cycles it means "light shall not pass" unlike "pass it all" of RPR)
            # that's why we check it with small value like 0.0001
            subsurface_radius = self.rpr_context.max_node_value(subsurface_radius, 0.0001)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_SSS_SCATTER_DISTANCE, subsurface_radius)
            # TODO: check with radius_scale = bpy.context.scene.unit_settings.scale_length * 0.1

            rpr_node.set_input(pyrprx.UBER_MATERIAL_SSS_MULTISCATTER, False)
            # these also need to be set for core SSS to work.
            rpr_node.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, subsurface)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, (1.0, 1.0, 1.0, 1.0))

        # Transmission -> Refraction
        if enabled(transmission):
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT, transmission)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_COLOR, base_color)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_ROUGHNESS, transmission_roughness)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_IOR, ior)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_THIN_SURFACE, False)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_CAUSTICS, True)

        if enabled(normal_map):
            rpr_node.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_NORMAL, normal_map)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_NORMAL, normal_map)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_NORMAL, normal_map)

        if enabled(clearcoat_normal_map):
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_NORMAL, clearcoat_normal_map)
        elif enabled(normal_map):
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_NORMAL, normal_map)

        return rpr_node

    def parse_node_mix(self, blender_node):
        factor = self.get_socket_value(blender_node, 0)

        if isinstance(factor, float):
            if math.isclose(factor, 0.0):
                return self.get_socket_value(blender_node, 1)

            if math.isclose(factor, 1.0):
                return self.get_socket_value(blender_node, 2)

        shader1 = self.get_socket_value(blender_node, 1)
        shader2 = self.get_socket_value(blender_node, 2)

        rpr_node = self.rpr_context.create_material_node(self.node_key(blender_node), pyrpr.MATERIAL_NODE_BLEND)
        rpr_node.set_input('weight', factor)
        rpr_node.set_input('color0', shader1)
        rpr_node.set_input('color1', shader2)

        return rpr_node

    def parse_node_blackbody(self, blender_node):
        # TODO: if temperature is node implement calculation kelvin_rgb through arithmetic nodes
        temperature = self.get_socket_default(blender_node, 'Temperature')
        return light_utils.convert_kelvins_to_rgb(temperature)

    def parse_node_bump(self, blender_node):
        normal = self.get_socket_link(blender_node, 'Normal')
        # TODO: This is temporary return value, should be implemented correctly

        return normal

    def parse_node_normal_map(self, blender_node):
        color = self.get_socket_value(blender_node, 'Color')
        # TODO: This is temporary return value, should be implemented correctly

        return color

    def parse_node_invert(self, blender_node):
        color = self.get_socket_value(blender_node, 'Color')
        fac = self.get_socket_value(blender_node, 'Fac')

        # conversion formula: color * (1.0 - fac) + (1.0 - color) * fac
        return self.rpr_context.add_node_value(
            self.rpr_context.mul_node_value(color, self.rpr_context.sub_node_value(1.0, fac)),
            self.rpr_context.mul_node_value(self.rpr_context.sub_node_value(1.0, color), fac)
        )

    def parse_node_bright_contrast(self, blender_node):
        color = self.get_socket_value(blender_node, 'Color')
        bright = self.get_socket_value(blender_node, 'Bright')
        contrast = self.get_socket_value(blender_node, 'Contrast')

        # TODO: This formula is not correct, need to fix this
        # conversion formula: color * (contrast + 1.0) + bright
        return self.rpr_context.add_node_value(
            self.rpr_context.mul_node_value(
                color,
                self.rpr_context.add_node_value(contrast, 1.0),
            ),
            bright
        )

    def parse_node_light_path(self, blender_node, socket):

        log.warn("LightPath currently not supported", self.material, blender_node, socket)

        # TODO: Implemented ligth path node parser
        return None

    def parse_node_light_falloff(self, blender_node, socket):
        strength = self.get_socket_default(blender_node, 'Strength')

        # TODO: Implemented light falloff node parser
        return strength

    def parse_node_tex_checker(self, blender_node, socket):
        scale = self.get_socket_value(blender_node, 'Scale')

        # TODO: Finish tex checker parser with scale value

        checker = self.rpr_context.create_material_node(self.node_key(blender_node, socket), pyrpr.MATERIAL_NODE_CHECKER_TEXTURE)

        if socket.name == 'Fac':
            return checker

        if socket.name == 'Color':
            color1 = self.get_socket_value(blender_node, 'Color1')
            color2 = self.get_socket_value(blender_node, 'Color2')

            # conversion formula: color1 * (1 - checker) + color2 * checker
            return self.rpr_context.add_node_value(
                self.rpr_context.mul_node_value(color1, self.rpr_context.sub_node_value(1.0, checker)),
                self.rpr_context.mul_node_value(color2, checker)
            )

        raise TypeError("Incorrect output socket", self.material, blender_node, socket)
