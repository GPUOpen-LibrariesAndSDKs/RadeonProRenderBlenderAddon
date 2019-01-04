import bpy
import numpy as np

import pyrpr
import pyrprx
from rprblender.utils import logging
from rprblender import utils


log = logging.Log(tag='NodeExport')


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


def export_blender_node(rpr_context, node, export_data=None):
    ''' here is where the magic happens.
    Use the json data to create rpr nodes from blender nodes '''
    result = None

    parsers = {
        'ShaderNodeBsdfPrincipled': parse_cycles_principled,
        'ShaderNodeTexImage': parse_image_texture,
        'ShaderNodeEmission': parse_cycles_emissive,
        'ShaderNodeBsdfDiffuse': parse_cycles_diffuse,
        # 'ShaderNodeRGB': parse_value_node,
    }

    log('export_blender_node: node {}'.format(node))
    try:
        node_key = utils.key(node)
        parser = parsers.get(node.bl_idname, None)
        if not parser:
            log.warn("Unsupported node type {}".format(node.bl_idname))
            return None
        result = parser(node_key, rpr_context, node)

#        for socket in node.inputs:
#            if socket.is_linked and len(socket.links):
#                input_node = socket.links[0].from_socket.node
#                log("\t[{}] socket {} linked to {}".format(node, socket, input_node))
#                result = export_blender_node(rpr_context, input_node)
#                if result:
#                    log("result: {}".format(result))
#                    return result
    except pyrpr.CoreError as e:
        log.warn("Exception {}\nReturning error material node".format(str(e)))
        result = create_fake_material("error_{}".format(node), rpr_context, color=(1, 0, 1, 1))

    log("[{}] node result {}".format(node, result))
    return result


def create_fake_material(node_key, rpr_context, color: tuple) -> pyrprx.Material:
    null_vector = (0, 0, 0, 0)
    rpr_mat = rpr_context.create_material(node_key, pyrprx.MATERIAL_UBER)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_COLOR, color)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, (1.0, 1.0, 1.0, 1.0))
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS, (0.5, 0.5, 0.5, 0.5))
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, null_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, null_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT, null_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT, null_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_WEIGHT, null_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_EMISSION_WEIGHT, null_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_SSS_WEIGHT, null_vector)
    return rpr_mat


def parse_image_texture(key, rpr_context, node) -> pyrprx.Material:
    rpr_node = rpr_context.create_material_node(key, pyrpr.MATERIAL_NODE_IMAGE_TEXTURE)
    image_object = node.image
    if image_object:
        try:
            rpr_image = utils.get_rpr_image(rpr_context, image_object)
        except ValueError as e:
            log.error(e)
            rpr_image = rpr_context.create_image_data('ErrorImage', np.full((2, 2, 4), (1, 0, 1, 1), dtype=np.float32))

        rpr_node.set_input('data', rpr_image)

    # rpr_node.set_input('uv', None)
    return rpr_node


def parse_cycles_emissive(key, rpr_context, node) -> pyrprx.Material:
    def get_value(name):
        socket = node.inputs[name]
        if socket:
            val = socket.default_value
            if isinstance(val, float) or isinstance(val, int):
                return (val, val, val, val)
            elif len(val) == 3:
                return (val[0], val[1], val[2], 1.0)
            elif len(val) == 4:
                return val[0:4]
            raise TypeError("Unknown socket '{}' value type '{}'".format(socket, type(socket)))

    color = get_value('Color')
    intensity = get_value('Strength')[0]
    color = (color[0] * intensity, color[1] * intensity, color[2] * intensity, color[0] * intensity)

    rpr_mat = rpr_context.create_material(key, pyrprx.MATERIAL_UBER)

    null_vector = (0, 0, 0, 0)
    one_vector = (1.0, 1.0, 1.0, 1.0)

    rpr_mat.set_input(pyrprx.UBER_MATERIAL_EMISSION_WEIGHT, one_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_EMISSION_COLOR, color)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_EMISSION_MODE, pyrprx.UBER_MATERIAL_EMISSION_MODE_DOUBLESIDED)

    rpr_mat.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, null_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, null_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, null_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT, null_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT, null_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_WEIGHT, null_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_SSS_WEIGHT, null_vector)

    return rpr_mat


def parse_cycles_diffuse(key, rpr_context, node):
    def get_value(name):
        socket = node.inputs[name]
        if socket:
            return socket.default_value

    color = tuple(get_value('Color'))
    roughness = get_value('Roughness')

    rpr_mat = rpr_context.create_material_node(key, pyrpr.MATERIAL_NODE_DIFFUSE)
    rpr_mat.set_input('color', color)
    rpr_mat.set_input('roughness', roughness)

    return rpr_mat


def parse_cycles_principled(key, rpr_context, node) -> pyrprx.Material:
    def get_value(name):
        socket = node.inputs[name]
        # log("input {} value is {}".format(name, socket.default_value))
        if socket:
            if socket.is_linked:
                log("getting linked node")
                try:
                    result = export_blender_node(rpr_context, socket.links[0].from_socket.node)
                except MaterialError as e:
                    log.warn("Unable to get socket {} value: {}".format(name, str(e)))
                    return (0, 0, 0, 0)
                log.debug("get_value({}): {}".format(name, result))
                if result:
                    return result
            val = socket.default_value
            if isinstance(val, float) or isinstance(val, int):
                return (val, val, val, val)
            elif len(val) == 3:
                return (val[0], val[1], val[2], 1.0)
            elif len(val) == 4:
                return val[0:4]
            raise TypeError("Unknown socket '{}' value type '{}'".format(socket, type(socket)))

#    def set_value(socket, value):
#        if value.is_image():

    base_color = get_value('Base Color')
    roughness = get_value('Roughness')
    subsurface = get_value('Subsurface')
    subsurface_radius = get_value('Subsurface Radius')
    subsurface_color = get_value('Subsurface Color')
    metalness = get_value('Metallic')
    specular = get_value('Specular')
    anisotropic = get_value('Anisotropic')
    anisotropic_rotation = get_value('Anisotropic Rotation')
    clearcoat = get_value('Clearcoat')
    clearcoat_roughness = get_value('Clearcoat Roughness')
    sheen = get_value('Sheen')
    sheen_tint = get_value('Sheen Tint')
    transmission = get_value('Transmission')
    ior = get_value('IOR')
    transmission_roughness = get_value('Transmission Roughness')

    radius_scale = bpy.context.scene.unit_settings.scale_length * .1
    subsurface_radius = (subsurface_radius[0] * radius_scale,
                         subsurface_radius[1] * radius_scale,
                         subsurface_radius[2] * radius_scale,
                         1.0)
    # Cycles default value of 0.5 is equal to RPR weight of 1.0
    specular = (specular[0]*2, specular[0]*2, specular[0]*2, specular[0]*2)
    # Glass need PBR reflection type and disabled diffuse channel
    is_not_glass = True if metalness or not transmission else False

    null_vector = (0, 0, 0, 0)
    one_vector = (1.0, 1.0, 1.0, 1.0)

    rpr_mat = rpr_context.create_material(key, pyrprx.MATERIAL_UBER)

    # Base color -> Diffuse (always on, except for glass)
    if is_not_glass:
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_COLOR, base_color)
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, one_vector)
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS, roughness)
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, null_vector)
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, null_vector)
    else:
        # TODO replace with mix of diffuse/refractive shaders with transmission as a mask/factor
        # TODO also adjust to core changes
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, null_vector)

    # Metallic -> Reflection (always on unless specular is set to non-physical 0.0)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT, specular)
    # mode 'metal' unless transmission is set and metallic is 0
    if is_not_glass:
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                              pyrprx.UBER_MATERIAL_REFLECTION_MODE_METALNESS)
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_METALNESS, metalness)
    else:
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                              pyrprx.UBER_MATERIAL_REFLECTION_MODE_PBR)
        rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_IOR, ior)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_COLOR, base_color)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ROUGHNESS, roughness)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY, anisotropic)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY_ROTATION, anisotropic_rotation)

    # Clearcloat -> Coating
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_COLOR, one_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_WEIGHT, clearcoat)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_ROUGHNESS, clearcoat_roughness)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_THICKNESS, null_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_TRANSMISSION_COLOR, null_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_MODE,
                          pyrprx.UBER_MATERIAL_COATING_MODE_PBR)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_COATING_IOR, ior)

    # Sheen -> Sheen
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_SHEEN_WEIGHT, sheen)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_SHEEN, base_color)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_SHEEN_TINT, sheen_tint)

    # No Emission for Cycles Principled BSDF
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_EMISSION_WEIGHT, null_vector)

    # Subsurface -> Subsurface
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_SSS_WEIGHT, subsurface)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_SSS_SCATTER_COLOR, subsurface_color)
    # these also need to be set for core SSS to work.
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, subsurface)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, one_vector)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_SSS_SCATTER_DISTANCE, subsurface_radius)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_SSS_MULTISCATTER, pyrpr.FALSE)

    # Transmission -> Refraction
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT, transmission)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFRACTION_COLOR, base_color)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFRACTION_ROUGHNESS, transmission_roughness)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFRACTION_IOR, ior)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFRACTION_THIN_SURFACE, pyrpr.FALSE)
    rpr_mat.set_input(pyrprx.UBER_MATERIAL_REFRACTION_CAUSTICS, pyrpr.TRUE)

    return rpr_mat

