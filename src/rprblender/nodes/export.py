import bpy

import pyrpr
import pyrprx
from rprblender.utils import logging
from rprblender import utils
from .blender_nodes import bsdf_diffuse_rules, emission_rules, bsdf_glossy_rules


log = logging.Log(tag='NodeExport', level='debug')


class MaterialError(Exception):
    pass


def dump_args(func):
    """This decorator dumps out the arguments passed to a function before calling it"""
    arg_names = func.__code__.co_varnames[:func.__code__.co_argcount]

    def echo_func(*args, **kwargs):
        log("<{}>: {}{}".format(
            func.__name__,
            tuple("{}={}".format(name, arg) for name, arg in zip(arg_names, args)),
            # args if args else "",
            " {}".format(kwargs.items()) if kwargs else "",
        ))
        return func(*args, **kwargs)
    return echo_func


# TODO use it at nodes info/plugin loading time
node_type_ids = {
    "RPR_MATERIAL_NODE_DIFFUSE": pyrpr.MATERIAL_NODE_DIFFUSE,
    "RPR_MATERIAL_NODE_REFLECTION": pyrpr.MATERIAL_NODE_REFLECTION,
    "RPR_MATERIAL_NODE_BLEND": pyrpr.MATERIAL_NODE_BLEND,
    "RPR_MATERIAL_NODE_ARITHMETIC": pyrpr.MATERIAL_NODE_ARITHMETIC,
    "RPRX_MATERIAL_UBER": pyrprx.MATERIAL_UBER,
}

# TODO use it at nodes info/plugin loading time
uber_input_ids = {
    "RPRX_UBER_MATERIAL_DIFFUSE_WEIGHT": pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT,
    "RPRX_UBER_MATERIAL_REFLECTION_WEIGHT": pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT,
    "RPRX_UBER_MATERIAL_REFRACTION_WEIGHT": pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT,
    "RPRX_UBER_MATERIAL_COATING_WEIGHT": pyrprx.UBER_MATERIAL_COATING_WEIGHT,
    "RPRX_UBER_MATERIAL_SHEEN_WEIGHT": pyrprx.UBER_MATERIAL_SHEEN_WEIGHT,
    "RPRX_UBER_MATERIAL_EMISSION_WEIGHT": pyrprx.UBER_MATERIAL_EMISSION_WEIGHT,
    "RPRX_UBER_MATERIAL_SSS_WEIGHT": pyrprx.UBER_MATERIAL_SSS_WEIGHT,
    "RPRX_UBER_MATERIAL_BACKSCATTER_WEIGHT": pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT,

    "RPRX_UBER_MATERIAL_DIFFUSE_COLOR": pyrprx.UBER_MATERIAL_DIFFUSE_COLOR,
    "RPRX_UBER_MATERIAL_DIFFUSE_ROUGHNESS": pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS,
    "RPRX_UBER_MATERIAL_REFLECTION_COLOR": pyrprx.UBER_MATERIAL_REFLECTION_COLOR,
    "RPRX_UBER_MATERIAL_REFLECTION_ROUGHNESS": pyrprx.UBER_MATERIAL_REFLECTION_ROUGHNESS,
    "RPRX_UBER_MATERIAL_REFLECTION_MODE": pyrprx.UBER_MATERIAL_REFLECTION_MODE,
    "RPRX_UBER_MATERIAL_REFLECTION_METALNESS": pyrprx.UBER_MATERIAL_REFLECTION_METALNESS,
    "RPRX_UBER_MATERIAL_EMISSION_COLOR": pyrprx.UBER_MATERIAL_EMISSION_COLOR,
    "RPRX_UBER_MATERIAL_EMISSION_MODE": pyrprx.UBER_MATERIAL_EMISSION_MODE,
}

rulesets = {
    'ShaderNodeBsdfDiffuse': bsdf_diffuse_rules,
    'ShaderNodeEmission': emission_rules,
    'ShaderNodeBsdfGlossy': bsdf_glossy_rules,
}


class MaterialExporter:
    def __init__(self, rpr_context, material_key):
        self.rpr_context = rpr_context
        self.material_key = material_key
        self.exported_nodes = {}

        self.static_parsers = {
            'ShaderNodeBsdfPrincipled': self.parse_cycles_principled,
            'ShaderNodeTexImage': self.parse_image_texture,
            'ShaderNodeRGB': self.parse_cycles_node_rgb,
            'ShaderNodeValue': self.parse_cycles_node_value,
            'ShaderNodeLightFalloff': self.dummy_light_falloff_node,
            'ShaderNodeTexChecker': self.dummy_node,
        }

    def export(self, entry_node, socket):
        log("Output socket {}".format(socket.name))
        return self.export_blender_node(entry_node, socket)

    def export_blender_node(self, blender_node, socket):
        log('export_blender_node: node {}'.format(blender_node))
        try:
            if blender_node.name in self.exported_nodes:
                log("Known node {}".format(blender_node.name))
                return self.exported_nodes[blender_node.name]

            rules = rulesets.get(blender_node.bl_idname, None)
            if rules:
                result = self.create_node_by_rules(rules, blender_node, socket)
            else:
                parser = self.static_parsers.get(blender_node.bl_idname, None)
                if not parser:
                    log.warn("Unsupported node type {}".format(blender_node.bl_idname))
                    return None

                result = parser(blender_node, socket)

            self.exported_nodes[blender_node.name] = result

        except pyrpr.CoreError as e:
            log.warn("Exception {}\nReturning error material node".format(str(e)))
            result = create_fake_material("error_{}".format(blender_node), self.rpr_context)

        return result

    def get_value(self, blender_node, socket_rules):
        socket_name = socket_rules['label']
        value_type = socket_rules['type']

        # UI fields
        if value_type == 'ui_list':
            return None

        # Input sockets only
        socket = blender_node.inputs[socket_name]
        # log("input {} value is {}".format(name, socket.default_value))
        if socket:
            if socket.is_linked:
                try:
                    result = self.export_blender_node(
                        socket.links[0].from_socket.node,
                        socket.links[0].from_socket,
                    )
                    if result:
                        return result
                except MaterialError as e:
                    log.warn("Unable to get socket {} linked value: {}".format(socket_name, str(e)))
                    pass
            elif value_type == 'link':
                log("\tNo link found for {}".format(socket_name))
                return None
            val = socket.default_value
            if isinstance(val, (int, float)):
                # if value_type == '':  # TODO add Math node subtypes
                return (val, val, val, val)
            elif len(val) == 3:
                return (val[0], val[1], val[2], 1.0)
            elif len(val) == 4:
                return val[0:4]
            raise TypeError("Unknown socket '{}' type '{}' of value {}".format(socket, type(socket), val))

    def collect_node_inputs(self, input_rules, blender_node):
        values = {}
        for name, input_rules in input_rules.items():
            values[name] = self.get_value(blender_node, input_rules)
        return values

    def create_node_by_rules(self, rules, blender_node, socket):
        node_key = (self.material_key, utils.key(blender_node))

        log("Parsing node {} using output socket {}".format(blender_node, socket.name))
        input_values = self.collect_node_inputs(rules['inputs'], blender_node)

        try:
            output_socket_info = rules['outputs'][socket.name]
            output_node_name = output_socket_info["node"]
        except KeyError:
            raise MaterialError("Wrong or absent output socket info for socket '{}'".format(socket.name))

        node_creator = RuledRPRNodeCreator(self.rpr_context, node_key, input_values, rules['nodes'])
        node = node_creator.create(output_node_name)

        return node

    def parse_image_texture(self, blender_node, socket) -> pyrprx.Material:
        node_key = (self.material_key, utils.key(blender_node))

        key = (self.material_key, utils.key(blender_node))

        rpr_node = self.rpr_context.create_material_node(key, pyrpr.MATERIAL_NODE_IMAGE_TEXTURE)

        image_object = blender_node.image
        if image_object:
            try:
                rpr_image = utils.get_rpr_image(self.rpr_context, image_object)
            except ValueError as e:  # return "Texture Error/Absence" image
                log.error(e)
                rpr_image = utils.create_flat_color_image_data(
                    rpr_context=self.rpr_context,
                    image_name='{}.ErrorImage'.format(key),
                    color=(1, 0, 1, 1))

            rpr_node.set_input('data', rpr_image)

        # TODO parse "Vector" UV mapping input socket
        # rpr_node.set_input('uv', None)
        return rpr_node

    def parse_cycles_principled(self, blender_node, socket) -> pyrprx.Material:
        rpr_node_type = pyrprx.MATERIAL_UBER
        input_rules = {
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

        values = self.collect_node_inputs(input_rules, blender_node)

        # check for 0 channel value(for Cycles it means "light shall not pass" unlike "pass it all" of RPR)
        radius_scale = bpy.context.scene.unit_settings.scale_length * 0.1
        subsurface_radius = (max(values['subsurface_radius'][0], 0.0001) * radius_scale,
                             max(values['subsurface_radius'][1], 0.0001) * radius_scale,
                             max(values['subsurface_radius'][2], 0.0001) * radius_scale,
                             1.0)
        # Cycles default value of 0.5 is equal to RPR weight of 1.0
        converted_specular = values['specular'][0]*2
        specular = (converted_specular, converted_specular, converted_specular, converted_specular)
        # Glass need PBR reflection type and disabled diffuse channel
        is_not_glass = True if values['metalness'] or not values['transmission'] else False

        node_key = (self.material_key, utils.key(blender_node))
        rpr_mat = self.rpr_context.create_material(node_key, rpr_node_type)

        # Base color -> Diffuse (always on, except for glass)
        if is_not_glass:
            rpr_mat.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_COLOR, values['base_color'])
            rpr_mat.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, 1.0)
            rpr_mat.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS, values['roughness'])
            rpr_mat.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, 0.0)
        else:
            # TODO replace with mix of diffuse/refractive shaders with transmission as a mask/factor
            # TODO also adjust to core changes
            rpr_mat.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, 0.0)

        # Metallic -> Reflection (always on unless specular is set to non-physical 0.0)
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT, specular)
        # mode 'metal' unless transmission is set and metallic is 0
        if is_not_glass:
            rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                                  pyrprx.UBER_MATERIAL_REFLECTION_MODE_METALNESS)
            rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_METALNESS, values['metalness'])
        else:
            rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                                  pyrprx.UBER_MATERIAL_REFLECTION_MODE_PBR)
            rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_IOR, values['ior'])
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_COLOR, values['base_color'])
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ROUGHNESS, values['roughness'])
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY, values['anisotropic'])
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY_ROTATION, values['anisotropic_rotation'])

        # Clearcloat -> Coating
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_COLOR, (1.0, 1.0, 1.0, 1.0))
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_WEIGHT, values['clearcoat'])
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_ROUGHNESS, values['clearcoat_roughness'])
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_THICKNESS, 0.0)
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_TRANSMISSION_COLOR, (0.0, 0.0, 0.0, 0.0))
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_MODE,
                              pyrprx.UBER_MATERIAL_COATING_MODE_PBR)
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_IOR, values['ior'])

        # Sheen -> Sheen
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_SHEEN_WEIGHT, values['sheen'])
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_SHEEN, values['base_color'])
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_SHEEN_TINT, values['sheen_tint'])

        # No Emission for Cycles Principled BSDF
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_EMISSION_WEIGHT, 0.0)

        # Subsurface -> Subsurface
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_SSS_WEIGHT, values['subsurface'])
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_SSS_SCATTER_COLOR, values['subsurface_color'])
        # these also need to be set for core SSS to work.
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, values['subsurface'])
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, (1.0, 1.0, 1.0, 1.0))
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_SSS_SCATTER_DISTANCE, subsurface_radius)
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_SSS_MULTISCATTER, pyrpr.FALSE)

        # Transmission -> Refraction
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT, values['transmission'])
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFRACTION_COLOR, values['base_color'])
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFRACTION_ROUGHNESS, values['transmission_roughness'])
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFRACTION_IOR, values['ior'])
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFRACTION_THIN_SURFACE, pyrpr.FALSE)
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFRACTION_CAUSTICS, pyrpr.TRUE)

        return rpr_mat


    def parse_cycles_node_socket_color(self, blender_node, socket) -> pyrprx.Material:
        val = blender_node.outputs[0].default_value
        return val[:]

    def parse_cycles_node_rgb(self, blender_node, socket) -> tuple:
        val = blender_node.outputs[0].default_value
        return val[:]

    def parse_cycles_node_value(self, blender_node, socket) -> tuple:
        val = blender_node.outputs[0].default_value
        return (val, val, val, val)

    # Nodes used by material preview render
    def dummy_light_falloff_node(self, blender_node, socket):
        return None

    def dummy_node(self, blender_node, socket):
        # TODO replace with buit-in checker texture
        return (1.0, 1.0, 1.0, 1.0)


class RuledRPRNodeCreator:
    def __init__(self, rpr_context, base_node_key, values, rules):
        self.rpr_context = rpr_context
        self.base_node_key = base_node_key
        self.rules = rules
        self.input_values = values

        self.nodes = {}

    def create(self, output_name):
        return self.create_rpr_node(output_name)

    def create_rpr_node(self, node_name):
        if node_name in self.nodes:
            return self.nodes[node_name]

        try:
            node_info = self.rules[node_name]
        except KeyError:
            raise MaterialError("Rules not found for rpr node '{}'".format(node_name))

        try:
            node_type = node_type_ids[node_info['type']]
        except KeyError:
            raise MaterialError("Unknown node type '{}'!".format(node_info['type']))

        node_key = "{}.{}".format(self.base_node_key, node_name)

        # create node
        is_uber_node = node_info['type'] == "RPRX_MATERIAL_UBER"
        if is_uber_node:
            rpr_node = self.rpr_context.create_material(node_key, pyrprx.MATERIAL_UBER)
        else:
            rpr_node = self.rpr_context.create_material_node(node_key, node_type)

        # filling node inputs
        for input_name, value_source in node_info['inputs'].items():
            if is_uber_node:
                input_id = uber_input_ids.get(input_name, None)
                if not input_id:
                    raise MaterialError("Unknown Uber material node input name '{}'!".format(input_name))
                input_name = input_id

            # is it the value source name?
            if isinstance(value_source, str):
                # static info
                if 'inputs.' in value_source:
                    target_name = value_source.split('inputs.')[1]
                    try:
                        value = self.input_values[target_name]
                    except KeyError:
                        raise MaterialError("Input '{}' value not found!".format(target_name))
                # links
                elif 'nodes.' in value_source:
                    target_name = value_source.split('nodes.')[1]
                    value = self.create_rpr_node(target_name)
                elif "scene." in value_source:  # for example, "scene.unit_settings.scale_length"
                    # TODO add scene data access
                    continue
                else:
                    continue
            else:  # nope. Constant value
                if isinstance(value_source, (tuple, list)):
                    value = tuple(value_source)
                else:  # int, float
                    value = value_source

            rpr_node.set_input(input_name, value)

        self.nodes[node_name] = rpr_node
        return rpr_node


def create_fake_material(node_key, rpr_context) -> pyrpr.MaterialNode:
    rpr_mat = rpr_context.create_material_node(node_key, pyrpr.MATERIAL_NODE_PASSTHROUGH)
    rpr_mat.set_input('color', (1, 0, 1, 1))
    return rpr_mat

