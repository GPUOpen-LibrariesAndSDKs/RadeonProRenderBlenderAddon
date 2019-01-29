import bpy
import pyrpr
import pyrprx

from . import MaterialError
from .export_by_rules import create_rpr_node_by_rules, rulesets
from rprblender.utils import logging
from rprblender.utils.material import find_output_node_in_tree
from rprblender import utils


log = logging.Log(tag='material', level='debug')


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
            log("Empty material tree '{}', skipping".format(self.material.name))
            return None

        log("export", self.material, tree)
        try:
            # looking for rpr output node
            output_node = find_output_node_in_tree(tree)
            if not output_node:
                raise MaterialError("No valid output node found", self.material)

            rpr_material = self.parse_output_node(output_node)
            if rpr_material:
                self.rpr_context.set_material_node_as_material(mat_key, rpr_material)

            return rpr_material

        except MaterialError as e:
            log.error(e)
            return create_fake_material(mat_key, self.rpr_context)

    #####
    # Support methods
    @staticmethod
    def set_rpr_input(rpr_node, name, value):
        if value is not None:
            try:
                rpr_node.set_input(name, value)
            except TypeError as e:  # in case user tried to do something strange like linking Uber node to Uber node
                raise MaterialError("Socket '{}' value assign error".
                                    format(name), rpr_node, e)

    @staticmethod
    def get_socket(node, name=None, index=None):
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

        log("get_socket({}, {}, {}): {}; linked {}".
            format(node, name, index, socket,
                   "{}; links number {}".format(socket.is_linked, len(socket.links)) if socket.is_linked else "False"))

        if socket.is_linked and len(socket.links) > 0:
            if socket.links[0].is_valid:
                return socket.links[0].from_socket

            log.error("Invalid link found: <{}>.{} to <{}>.{}".
                      format(socket.links[0].from_node.name, socket.links[0].from_socket.name,
                             socket.links[0].to_node.name, socket.links[0].to_socket.name))
        return None

    def node_key(self, node):
        return (utils.key(self.material), node.name)

    def get_socket_value(self, node, socket_name):
        socket = node.inputs[socket_name]

        if socket.is_linked and len(socket.links) > 0:
            if socket.links[0].is_valid:
                return self.parse_node(socket.links[0].from_node, socket.links[0].from_socket)

            log.error("Invalid link found: <{}>.{} to <{}>.{}".
                      format(socket.links[0].from_node.name, socket.links[0].from_socket.name,
                             socket.links[0].to_node.name, socket.links[0].to_socket.name))

        val = socket.default_value
        if isinstance(val, (int, float)):
            return float(val)
        elif len(val) in (3, 4):
            return tuple(val)

        log.warn("Unsupported socket value", self.material, node, socket_name, val)
        return None

    #####
    # Nodes parsing methods

    def parse_output_node(self, node):
        surface_socket = self.get_socket(node, name='Surface')  # 'Surface'
        if not surface_socket:
            raise MaterialError("No input for Surface socket", self.material, node)

        log("parse_output_node", self.material, node, surface_socket, surface_socket.node)

        rpr_node = self.parse_node(surface_socket.node, surface_socket)

        # TODO: Parse other sockets: volume and displacement

        return rpr_node

    def parse_node(self, node, socket):
        key = self.node_key(node)
        rpr_node = self.rpr_context.material_nodes.get(key, None)
        if rpr_node:
            return rpr_node

        # Can we export node using rules?
        rules = rulesets.get(node.bl_idname, None)
        if rules:
            return self.create_node_by_rules(node, rules, socket)

        # Can we export it using specific parser?
        static_parsers = {
            'ShaderNodeBsdfPrincipled': self.parse_cycles_principled,
            'ShaderNodeBsdfDiffuse': self.parse_node_diffuse,
            'ShaderNodeTexImage': self.parse_image_texture,
            'ShaderNodeRGB': self.parse_cycles_node_rgb,
            'ShaderNodeValue': self.parse_cycles_node_value,
            # dummy nodes for unsupported nodes for material preview
            'ShaderNodeLightFalloff': self.dummy_light_falloff_node,
            'ShaderNodeTexChecker': self.dummy_node,
        }
        parser = static_parsers.get(node.bl_idname)
        if parser:
            return parser(node)

        log.warn("Ignoring unsupported node", self.material, node, node.bl_idname)
        return None

    def create_node_by_rules(self, blender_node, rules, socket):
        node_key = self.node_key(blender_node)

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
        def get_value(socket_name):
            return self.get_socket_value(blender_node, socket_name)

        rpr_node = self.rpr_context.create_material_node(self.node_key(blender_node), pyrpr.MATERIAL_NODE_DIFFUSE)

        color = get_value('Color')
        roughness = get_value('Roughness')

        self.set_rpr_input(rpr_node, 'color', color)
        self.set_rpr_input(rpr_node, 'roughness', roughness)

        return rpr_node

    def parse_image_texture(self, blender_node):
        key = self.node_key(blender_node)
        rpr_node = self.rpr_context.create_material_node(key, pyrpr.MATERIAL_NODE_IMAGE_TEXTURE)

        image_object = blender_node.image
        if image_object:
            try:
                rpr_image = utils.get_rpr_image(self.rpr_context, image_object)
            except ValueError as e:  # texture loading error, return "Texture Error/Absence" image
                log.error(e)
                return (1.0, 0.0, 1.0, 1.0)

            rpr_node.set_input('data', rpr_image)

        # TODO parse "Vector" UV mapping input socket
        # rpr_node.set_input('uv', None)
        return rpr_node

    def parse_cycles_principled(self, blender_node) -> pyrprx.Material:
        node_key = self.node_key(blender_node)

        principled_inputs = {
            'base_color': {'label': 'Base Color', 'type': 'color'},
            'roughness': {'label': 'Roughness', 'type': 'float'},
            'subsurface': {'label': 'Subsurface', 'type': 'float'},
            'subsurface_radius': {'label': 'Subsurface Radius', 'type': 'vector3'},
            'subsurface_color': {'label': 'Subsurface Color', 'type': 'color'},
            'metalness': {'label': 'Metallic', 'type': 'float'},
            'specular': {'label': 'Specular', 'type': 'float'},
            'anisotropic': {'label': 'Anisotropic', 'type': 'float'},
            'anisotropic_rotation': {'label': 'Anisotropic Rotation', 'type': 'float'},
            'clearcoat': {'label': 'Clearcoat', 'type': 'float'},
            'clearcoat_roughness': {'label': 'Clearcoat Roughness', 'type': 'float'},
            'sheen': {'label': 'Sheen', 'type': 'float'},
            'sheen_tint': {'label': 'Sheen Tint', 'type': 'float'},
            'transmission': {'label': 'Transmission', 'type': 'float'},
            'ior': {'label': 'IOR', 'type': 'float'},
            'transmission_roughness': {'label': 'Transmission Roughness', 'type': 'float'},
            'normal_map': {'label': 'Normal', 'type': 'link'},
            'clearcoat_normal_map': {'label': 'Clearcoat Normal', 'type': 'link'},
            # tangent map for anisotropic rotation is not supported
        }
        values = {}
        for key, entry in principled_inputs.items():
            values[key] = self.get_socket_value(blender_node, entry['label'])

        # Normal maps accept node links only, not values
        # Uber raises Core error if Normal inut assigned with tuple
        # TODO: find a better way to handle invalid Normal socket links
        if values['normal_map'] == (0.0, 0.0, 0.0):
            values['normal_map'] = None
        if values['clearcoat_normal_map'] == (0.0, 0.0, 0.0):
            values['clearcoat_normal_map'] = None

        # check for 0 channel value(for Cycles it means "light shall not pass" unlike "pass it all" of RPR)
        radius_scale = bpy.context.scene.unit_settings.scale_length * 0.1
        # TODO use the RPR Arithmetic node instead
        subsurface_radius = (max(values['subsurface_radius'][0], 0.0001) * radius_scale,
                             max(values['subsurface_radius'][1], 0.0001) * radius_scale,
                             max(values['subsurface_radius'][2], 0.0001) * radius_scale,
                             1.0)
        # Cycles default value of 0.5 is equal to RPR weight of 1.0
        converted_specular = values['specular'] * 2
        # Glass need PBR reflection type and disabled diffuse channel
        is_not_glass = True if values['metalness'] or not values['transmission'] else False

        rpr_mat = self.rpr_context.create_x_material_node(node_key, pyrprx.MATERIAL_UBER)

        # Base color -> Diffuse (always on, except for glass)
        if is_not_glass:
            self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_DIFFUSE_COLOR, values['base_color'])
            self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, 1.0)
            self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS, values['roughness'])
            self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, 0.0)
        else:
            # TODO replace with mix of diffuse/refractive shaders with transmission as a mask/factor
            # TODO also adjust to core changes
            self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, 0.0)

        # Metallic -> Reflection (always on unless specular is set to non-physical 0.0)
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT, converted_specular)
        # mode 'metal' unless transmission is set and metallic is 0
        if is_not_glass:
            self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                               pyrprx.UBER_MATERIAL_REFLECTION_MODE_METALNESS)
            self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFLECTION_METALNESS, values['metalness'])
        else:
            self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                               pyrprx.UBER_MATERIAL_REFLECTION_MODE_PBR)
            self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFLECTION_IOR, values['ior'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFLECTION_COLOR, values['base_color'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFLECTION_ROUGHNESS, values['roughness'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY, values['anisotropic'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY_ROTATION,
                           values['anisotropic_rotation'])

        # Clearcloat -> Coating
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_COATING_COLOR, (1.0, 1.0, 1.0, 1.0))
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_COATING_WEIGHT, values['clearcoat'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_COATING_ROUGHNESS, values['clearcoat_roughness'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_COATING_THICKNESS, 0.0)
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_COATING_TRANSMISSION_COLOR, (0.0, 0.0, 0.0, 0.0))
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_COATING_MODE,
                           pyrprx.UBER_MATERIAL_COATING_MODE_PBR)
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_COATING_IOR, values['ior'])

        # Sheen -> Sheen
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_SHEEN_WEIGHT, values['sheen'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_SHEEN, values['base_color'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_SHEEN_TINT, values['sheen_tint'])

        # No Emission for Cycles Principled BSDF
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_EMISSION_WEIGHT, 0.0)

        # Subsurface -> Subsurface
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_SSS_WEIGHT, values['subsurface'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_SSS_SCATTER_COLOR, values['subsurface_color'])
        # these also need to be set for core SSS to work.
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, values['subsurface'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, (1.0, 1.0, 1.0, 1.0))
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_SSS_SCATTER_DISTANCE, subsurface_radius)
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_SSS_MULTISCATTER, pyrpr.FALSE)

        # Transmission -> Refraction
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT, values['transmission'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFRACTION_COLOR, values['base_color'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFRACTION_ROUGHNESS, values['transmission_roughness'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFRACTION_IOR, values['ior'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFRACTION_THIN_SURFACE, pyrpr.FALSE)
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFRACTION_CAUSTICS, pyrpr.TRUE)

        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_DIFFUSE_NORMAL, values['normal_map'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFLECTION_NORMAL, values['normal_map'])
        self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_REFRACTION_NORMAL, values['normal_map'])

        if values['clearcoat_normal_map']:
            self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_COATING_NORMAL, values['clearcoat_normal_map'])
        else:
            self.set_rpr_input(rpr_mat, pyrprx.UBER_MATERIAL_COATING_NORMAL, values['normal_map'])

        return rpr_mat

    def parse_cycles_node_socket_color(self, blender_node):
        val = blender_node.outputs[0].default_value
        return tuple(val)

    def parse_cycles_node_rgb(self, blender_node):
        val = blender_node.outputs[0].default_value
        return tuple(val)

    def parse_cycles_node_value(self, blender_node):
        val = blender_node.outputs[0].default_value
        return float(val)

    # Nodes used by material preview render
    def dummy_light_falloff_node(self, blender_node):
        """Cycles node to control light sources falloff. Could not be reproduced by RPR"""
        return 1.0

    def dummy_node(self, blender_node):
        # TODO replace with RPR checker texture node
        return 1.0, 1.0, 1.0, 1.0


def create_fake_material(node_key, rpr_context) -> pyrpr.MaterialNode:
    rpr_mat = rpr_context.create_material_node(node_key, pyrpr.MATERIAL_NODE_PASSTHROUGH)
    rpr_mat.set_input('color', (1, 0, 1, 1))
    return rpr_mat
