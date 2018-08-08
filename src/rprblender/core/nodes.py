import os
import io
import math
import traceback
import numpy as np
from rprblender import config

import bpy
import pyrpr

from rprblender import logging
from enum import Enum, IntEnum
import rprblender.node_editor
import rprblender.ui
import rprblender.core.image
from rprblender.nodes import get_node_groups_by_id

from . import buffer

import pyrprx

def log_mat(*args):
    logging.debug(*args, tag='material')


def unit_clamp(val):
    return max(-1, min(val, 1))


def safe_mod(a, b):
    if b == 0:
        return 0
    return math.fmod(a, b)


class ValueType(Enum):
    unknown = 0
    node = 1
    vector = 2
    image = 3

class MaterialError(RuntimeError):
    pass

class ShaderType(IntEnum):
    DIFFUSE = pyrpr.MATERIAL_NODE_DIFFUSE
    EMISSIVE = pyrpr.MATERIAL_NODE_EMISSIVE
    DOUBLESIDED = pyrpr.MATERIAL_NODE_TWOSIDED
    VOLUME = pyrpr.MATERIAL_NODE_VOLUME
    MICROFACET = pyrpr.MATERIAL_NODE_MICROFACET
    MICROFACET_REFRACTION = pyrpr.MATERIAL_NODE_MICROFACET_REFRACTION
    BLEND = pyrpr.MATERIAL_NODE_BLEND
    DIFFUSE_REFRACTION = pyrpr.MATERIAL_NODE_DIFFUSE_REFRACTION
    ORENNAYAR = pyrpr.MATERIAL_NODE_ORENNAYAR
    REFLECTION = pyrpr.MATERIAL_NODE_REFLECTION
    REFRACTION = pyrpr.MATERIAL_NODE_REFRACTION
    TRANSPARENT = pyrpr.MATERIAL_NODE_TRANSPARENT
    WARD = pyrpr.MATERIAL_NODE_WARD
    UBER = pyrpr.MATERIAL_NODE_STANDARD
    UBER2 = 0xFF


class NodeType(IntEnum):
    IMAGE_TEXTURE = pyrpr.MATERIAL_NODE_IMAGE_TEXTURE
    ARITHMETIC = pyrpr.MATERIAL_NODE_ARITHMETIC
    INPUT_LOOKUP = pyrpr.MATERIAL_NODE_INPUT_LOOKUP
    BLEND_VALUE = pyrpr.MATERIAL_NODE_BLEND_VALUE
    NORMAL_MAP = pyrpr.MATERIAL_NODE_NORMAL_MAP
    BUMP_MAP = pyrpr.MATERIAL_NODE_BUMP_MAP
    NOISE2D_TEXTURE = pyrpr.MATERIAL_NODE_NOISE2D_TEXTURE
    GRADIENT_TEXTURE = pyrpr.MATERIAL_NODE_GRADIENT_TEXTURE
    CHECKER_TEXTURE = pyrpr.MATERIAL_NODE_CHECKER_TEXTURE
    DOT_TEXTURE = pyrpr.MATERIAL_NODE_DOT_TEXTURE
    FRESNEL_SCHLICK = pyrpr.MATERIAL_NODE_FRESNEL_SCHLICK
    FRESNEL = pyrpr.MATERIAL_NODE_FRESNEL
    BUFFER_SAMPLER = pyrpr.MATERIAL_NODE_BUFFER_SAMPLER
    AO_MAP = pyrpr.MATERIAL_NODE_AO_MAP


class OperatorType(IntEnum):
    ADD = pyrpr.MATERIAL_NODE_OP_ADD
    SUB = pyrpr.MATERIAL_NODE_OP_SUB
    MUL = pyrpr.MATERIAL_NODE_OP_MUL
    SIN = pyrpr.MATERIAL_NODE_OP_SIN
    COS = pyrpr.MATERIAL_NODE_OP_COS
    TAN = pyrpr.MATERIAL_NODE_OP_TAN
    SELECT_X = pyrpr.MATERIAL_NODE_OP_SELECT_X
    SELECT_Y = pyrpr.MATERIAL_NODE_OP_SELECT_Y
    SELECT_Z = pyrpr.MATERIAL_NODE_OP_SELECT_Z
    SELECT_W = pyrpr.MATERIAL_NODE_OP_SELECT_W
    COMBINE = pyrpr.MATERIAL_NODE_OP_COMBINE
    DOT3 = pyrpr.MATERIAL_NODE_OP_DOT3
    DOT4 = pyrpr.MATERIAL_NODE_OP_DOT4
    CROSS3 = pyrpr.MATERIAL_NODE_OP_CROSS3
    LENGTH3 = pyrpr.MATERIAL_NODE_OP_LENGTH3
    NORMALIZE3 = pyrpr.MATERIAL_NODE_OP_NORMALIZE3
    POW = pyrpr.MATERIAL_NODE_OP_POW
    ACOS = pyrpr.MATERIAL_NODE_OP_ACOS
    ASIN = pyrpr.MATERIAL_NODE_OP_ASIN
    ATAN = pyrpr.MATERIAL_NODE_OP_ATAN  # binary?
    AVERAGE_XYZ = pyrpr.MATERIAL_NODE_OP_AVERAGE_XYZ  # ?
    AVERAGE = pyrpr.MATERIAL_NODE_OP_AVERAGE  # ?
    MIN = pyrpr.MATERIAL_NODE_OP_MIN
    MAX = pyrpr.MATERIAL_NODE_OP_MAX
    FLOOR = pyrpr.MATERIAL_NODE_OP_FLOOR
    MOD = pyrpr.MATERIAL_NODE_OP_MOD
    ABS = pyrpr.MATERIAL_NODE_OP_ABS
    DIV = pyrpr.MATERIAL_NODE_OP_DIV


class LookupType(IntEnum):
    uv = pyrpr.MATERIAL_NODE_LOOKUP_UV
    position = pyrpr.MATERIAL_NODE_LOOKUP_P
    incident = pyrpr.MATERIAL_NODE_LOOKUP_INVEC
    out_vector = pyrpr.MATERIAL_NODE_LOOKUP_OUTVEC


class Value:
    type = ValueType.unknown

    def is_vector(self):
        return self.type == ValueType.vector

    def is_node(self):
        return self.type == ValueType.node

    def is_image(self):
        return self.type == ValueType.image


class ValueVector(Value):
    type = ValueType.vector

    def __init__(self, x=0, y=0, z=0, w=0):
        self.x = x
        self.y = y
        self.z = z
        self.w = w

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        else:
            return self.x == other.x and self.y == other.y \
                and self.z == other.z and self.w == other.w

    def __str__(self):
        return "<ValueVector: %s>" % ((self.x, self.y, self.z, self.w),)


class ValueNode(Value):
    type = ValueType.node

    def __init__(self, rpr_node):
        self.node = rpr_node


class ValueImage(Value):
    type = ValueType.image

    def __init__(self, image):
        self.image = image


class Image:
    handle = None

    def __init__(self, handle):
        assert handle
        self.handle = handle

    def get_handle(self):
        return self.handle


class Node:
    handle = None
    rprx_context = None

    def __init__(self, handle):
        assert handle
        self.handle = handle

    def set_rprx_context(self, rprx_context_temp):
        self.rprx_context = rprx_context_temp

    def set_value(self, name, value):
        if value.is_vector():
            log_mat('  set_value : set "%s" rpr vector from value(%f, %f, %f, %f,)'
                    % (name, value.x, value.y, value.z, value.w))
            pyrpr.MaterialNodeSetInputF(self.get_handle(), name, value.x, value.y, value.z, value.w)
        elif value.is_node():
            log_mat('  set_value : set "%s" rpr node from value(%s)' % (name, value))
            self.set_node(name, value.node)
        elif value.is_image():
            log_mat('  set_value : set "%s" rpr image from value(%s)' % (name, value))
            self.set_image(name, value.image)
        else:
            log_mat('set_value : none "%s" (%s)' % (name, value))

    def set_value_rprx(self, parameter, value):
        if value.is_vector():
            log_mat('  set_value_rprx : set "%s" rpr vector from value(%f, %f, %f, %f,)'
                    % (parameter, value.x, value.y, value.z, value.w))
            pyrprx.MaterialSetParameterF(self.rprx_context, self.get_handle(),
                                          parameter,
                                          value.x, value.y, value.z, value.w)
        elif value.is_node():
            node = value.node
            pyrprx.xMaterialSetParameterN(self.rprx_context, self.get_handle(), parameter,
                                          node.get_handle() if node.get_handle() else None)
        elif value.is_image():
            image = value.image
            pyrprx.xMaterialSetParameterN(self.rprx_context, self.get_handle(), parameter,
                                          image.get_handle() if image.get_handle() else None)
        else:
            log_mat('set_value : none "%s" (%s)' % (parameter, value))



    def set_int(self, name, int_val):
        log_mat('  set_int : set "%s" int(%d)' % (name, int_val))
        pyrpr.MaterialNodeSetInputU(self.get_handle(), name, int_val)

    def set_int_rprx(self, parameter, int_val):
        log_mat('  set_int : set "%s" int(%d)' % (parameter, int_val))
        pyrprx.xMaterialSetParameterU(self.rprx_context, self.get_handle(), parameter, int_val)

    def set_node(self, name, rpr_node):
        assert self.get_handle()
        log_mat('  set_node : set node to param "%s"' % name)
        if rpr_node.rprx_context == None:
            pyrpr.MaterialNodeSetInputN(self.get_handle(), name,
                                        rpr_node.get_handle() if rpr_node.get_handle() else None)
        else:
            # attach rprx shader output to some material's input
            # note: there's no call to rprxShapeDetachMaterial
            assert rpr_node.get_handle()
            pyrprx.xMaterialAttachMaterial(rpr_node.rprx_context, self.get_handle(), name, rpr_node.get_handle())
            pyrprx.xMaterialCommit(rpr_node.rprx_context, rpr_node.get_handle())

    def set_node_rprx(self, parameter, rpr_node):
        pyrprx.xMaterialSetParameterN(self.rprx_context, self.get_handle(), parameter,
                                      rpr_node.get_handle() if rpr_node.get_handle() else None)

    def set_image(self, name, image):
        assert self.get_handle()
        log_mat('  set_node : set node to param "%s"' % name)
        pyrpr.MaterialNodeSetInputImageData(self.get_handle(), name, image.get_handle() if image.get_handle() else None)

    def get_handle(self):
        return self.handle


class ImageTextureNode(Node):
    def __init__(self, mat):
        super().__init__(mat.create_material_node(NodeType.IMAGE_TEXTURE))

    def set_map(self, image):
        self.set_value(b'data', image)

    def set_uv(self, uv):
        if uv.type != ValueType.unknown:
            self.set_value(b'uv', uv)


class LookupNode(Node):
    def __init__(self, mat, type):
        super().__init__(mat.create_material_node(NodeType.INPUT_LOOKUP))
        self.set_int(b'value', type)


class NormalMapNode(Node):
    def __init__(self, mat):
        super().__init__(mat.create_material_node(NodeType.NORMAL_MAP))

    def set_map(self, value):
        if value:
            self.set_value(b'color', value)


class BumpMapNode(Node):
    def __init__(self, mat):
        super().__init__(mat.create_material_node(NodeType.BUMP_MAP))

    def set_map(self, value):
        if value:
            self.set_value(b'color', value)

    def set_bumpscale(self, value):
        self.set_value(b'bumpscale', value)


class ArithmeticNode(Node):
    def __init__(self, mat, a, b, op):
        super().__init__(mat.create_material_node(NodeType.ARITHMETIC))

        self.set_int(b'op', op)
        self.set_value(b'color0', a)
        if b is not None:
            self.set_value(b'color1', b)


class BlendNode(Node):
    def __init__(self, mat, a, b, weight):
        super().__init__(mat.create_material_node(NodeType.BLEND_VALUE))
        self.set_value(b'weight', weight)
        self.set_value(b'color0', a)
        self.set_value(b'color1', b)


class GradientTextureNode(Node):
    def __init__(self, mat, color1, color2, uv):
        super().__init__(mat.create_material_node(NodeType.GRADIENT_TEXTURE))
        self.set_value(b'color0', color1)
        self.set_value(b'color1', color2)
        if uv.type != ValueType.unknown:
            self.set_value(b'uv', uv)


class Noise2DTextureNode(Node):
    def __init__(self, mat, uv):
        super().__init__(mat.create_material_node(NodeType.NOISE2D_TEXTURE))
        if uv.type != ValueType.unknown:
            self.set_value(b'uv', uv)


class CheckerTextureNode(Node):
    def __init__(self, mat, uv):
        super().__init__(mat.create_material_node(NodeType.CHECKER_TEXTURE))
        if uv.type != ValueType.unknown:
            self.set_value(b'uv', uv)


class DotTextureNode(Node):
    def __init__(self, mat, uv):
        super().__init__(mat.create_material_node(NodeType.DOT_TEXTURE))
        if uv.type != ValueType.unknown:
            self.set_value(b'uv', uv)


class FresnelSchlickNode(Node):
    def __init__(self, mat, reflectance, normal, invec):
        super().__init__(mat.create_material_node(NodeType.FRESNEL_SCHLICK))
        self.set_value(b'reflectance', reflectance)
        self.set_value(b'normal', normal)
        self.set_value(b'invec', invec)


class FresnelNode(Node):
    def __init__(self, mat, ior, normal, invec):
        super().__init__(mat.create_material_node(NodeType.FRESNEL))
        self.set_value(b'ior', ior)
        self.set_value(b'normal', normal)
        self.set_value(b'invec', invec)


class BufferSamplerShader(Node):
    def __init__(self, mat, uv, buffer):
        super().__init__(mat.create_material_node(NodeType.BUFFER_SAMPLER))
        # scale the uv by buffer size
        self.set_value(b'uv', mat.mul_value(uv, ValueVector(config.ramp_buffer_size)))
        pyrpr.MaterialNodeSetInputBufferData(self.get_handle(), b'data', buffer._get_handle())
 

class AOMapShader(Node):
    def __init__(self, mat, radius, side):
        super().__init__(mat.create_material_node(NodeType.AO_MAP))
        self.set_value(b'radius', radius)
        self.set_value(b'side', side)


class Shader(Node):
    type = None

    def __init__(self, mat, type):
        if type == ShaderType.UBER2:
            super().__init__(mat.create_uber_material())
            super().set_rprx_context(mat.manager.get_uber_rprx_context())
        else:
            super().__init__(mat.create_material_node(type))
        self.type = type


class DiffuseShader(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.DIFFUSE)

    def set_color(self, value):
        self.set_value(b"color", value)

    def set_roughness(self, value):
        self.set_value(b"roughness", value)

    def set_normal(self, value):
        self.set_value(b"normal", value)


class EmissiveShader(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.EMISSIVE)

    def set_color(self, value):
        self.set_value(b"color", value)


class VolumeShader(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.VOLUME)

    def set_sigmas(self, value):
        self.set_value(b"sigmas", value)

    def set_sigmaa(self, value):
        self.set_value(b"sigmaa", value)

    def set_emission(self, value):
        self.set_value(b"emission", value)

    def set_g(self, value):
        self.set_value(b"g", value)

    def set_multiscatter(self, value):
        self.set_value(b"multiscatter", value)


class MicrofacetShader(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.MICROFACET)

    def set_color(self, value):
        self.set_value(b"color", value)

    def set_normal(self, value):
        self.set_value(b"normal", value)

    def set_roughness(self, value):
        self.set_value(b"roughness", value)


class MicrofacetRefractionShader(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.MICROFACET_REFRACTION)

    def set_color(self, value):
        self.set_value(b"color", value)

    def set_normal(self, value):
        self.set_value(b"normal", value)

    def set_roughness(self, value):
        self.set_value(b"roughness", value)

    def set_ior(self, value):
        self.set_value(b"ior", value)


class BlendShader(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.BLEND)

    def set_shader1(self, shader):
        self.set_node(b"color0", shader)

    def set_shader2(self, shader):
        self.set_node(b"color1", shader)

    def set_weight(self, value):
        self.set_value(b"weight", value)


class DoubleSidedShader(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.DOUBLESIDED)

    def set_shader_front(self, shader):
        self.set_node(b"frontface", shader)

    def set_shader_back(self, shader):
        self.set_node(b"backface", shader)


class DiffuseRefractionShader(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.DIFFUSE_REFRACTION)

    def set_color(self, value):
        self.set_value(b"color", value)

    def set_normal(self, value):
        self.set_value(b"normal", value)


class OrenNayarShader(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.ORENNAYAR)

    def set_color(self, value):
        self.set_value(b"color", value)

    def set_normal(self, value):
        self.set_value(b"normal", value)

    def set_roughness(self, value):
        self.set_value(b"roughness", value)


class RefractionShader(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.REFRACTION)

    def set_color(self, value):
        self.set_value(b"color", value)

    def set_normal(self, value):
        self.set_value(b"normal", value)

    def set_ior(self, value):
        self.set_value(b"ior", value)


class ReflectionShader(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.REFLECTION)

    def set_color(self, value):
        self.set_value(b"color", value)

    def set_normal(self, value):
        self.set_value(b"normal", value)


class TransparentShader(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.TRANSPARENT)

    def set_color(self, value):
        self.set_value(b"color", value)


class WardShader(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.WARD)

    def set_color(self, value):
        self.set_value(b"color", value)

    def set_rotation(self, value):
        self.set_value(b"rotation", value)

    def set_roughness_x(self, value):
        self.set_value(b"roughness_x", value)

    def set_roughness_y(self, value):
        self.set_value(b"roughness_y", value)

    def set_normal(self, value):
        self.set_value(b"normal", value)


class UberShader(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.UBER)

    # DIFFUSE BASE
    def set_diffuse_color(self, value):
        self.set_value(b"diffuse.color", value)

    def set_diffuse_normal(self, value):
        self.set_value(b"diffuse.normal", value)

    # GLOSSY REFLECTIONS
    def set_reflect_color(self, value):
        self.set_value(b"glossy.color", value)

    def set_reflect_ior(self, value):
        self.set_value(b"weights.glossy2diffuse", value)

    def set_reflect_roughness_x(self, value):
        self.set_value(b"glossy.roughness_x", value)

    def set_reflect_roughness_y(self, value):
        self.set_value(b"glossy.roughness_y", value)

    def set_reflect_normal(self, value):
        self.set_value(b"glossy.normal", value)

    # CLEAR COAT
    def set_coat_color(self, value):
        self.set_value(b"clearcoat.color", value)

    def set_coat_ior(self, value):
        self.set_value(b"weights.clearcoat2glossy", value)

    def set_coat_normal(self, value):
        self.set_value(b"clearcoat.normal", value)

    # REFRACTION
    def set_refraction(self, value):
        self.set_value(b"weights.diffuse2refraction", value)

    def set_refraction_color(self, value):
        self.set_value(b"refraction.color", value)

    def set_refraction_ior(self, value):
        self.set_value(b"refraction.ior", value)

    def set_refraction_roughness(self, value):
        self.set_value(b"refraction.roughness", value)

    def set_refraction_normal(self, value):
        self.set_value(b"refraction.normal", value)

    # TRANSPARENCY
    def set_transparency_color(self, value):
        self.set_value(b"transparency.color", value)

    def set_transparency_level(self, value):
        self.set_value(b"weights.transparency", value)



class UberShader2(Shader):
    def __init__(self, mat):
        super().__init__(mat, ShaderType.UBER2)


class Material:

    def __init__(self, manager):
        self.shader = None
        self.manager = manager
        self.node_list = []
        self.reroute_list = {}
        self.node_groups_list = {}
        self.has_error = False
        self.volume_handle = None
        self.displacement = None
        self.name = ""

    def __del__(self):
        if self.shader is not None and self.shader.type == ShaderType.UBER2 and self.shader.rprx_context:
            pyrprx.MaterialDelete(self.shader.rprx_context, self.shader.get_handle())

    def detach_from_shape(self, shape):
        if self.shader != None and self.shader.type == ShaderType.UBER2 and self.shader.rprx_context:
            pyrprx.ShapeDetachMaterial(self.shader.rprx_context, shape, self.shader.get_handle())
        self.shader = None  # this requires to prevent calling MaterialDelete if ShapeDetachMaterial was called

    def get_handle(self):
        return None if self.shader == None else self.shader.get_handle()

    def get_volume(self):
        return self.volume_handle

    def get_displacement(self):
        return self.displacement

    def is_error_show(self):
        dev = bpy.context.scene.rpr.dev
        show_errors = dev.show_rpr_materials_with_errors if self.output_node_was_parsed else dev.show_cycles_materials_with_errors
        return show_errors

    def create_error_shader(self):
        val = self.create_error_value()
        if self.is_error_show():
            shader = EmissiveShader(self)
        else:
            shader = DiffuseShader(self)

        shader.set_color(val)
        return shader

    def create_error_value(self):
        if self.is_error_show():
            return ValueVector(1, 0, 1, 1)
        else:
            return ValueVector(0.5, 0.5, 0.5, 1)

    def parse_cycles_shader_OutputMaterial(self, blender_node):
        socket = self.get_socket(blender_node, 'Surface')
        assert socket
        return self.parse_node(socket)

    def parse_cycles_shader_node_BsdfDiffuse(self, blender_node):
        log_mat('parse_cycles_shader_node_BsdfDiffuse...')
        shader = DiffuseShader(self)
        val = self.get_value(blender_node, 'Color')
        log_mat("   diffuse_color: %s" % val)
        shader.set_color(val)
        return shader

    def parse_cycles_shader_node_MixShader(self, blender_node):
        log_mat('parse_cycles_shader_node_MixShader...')
        socket1 = self.get_socket(blender_node, '', 1)
        shader1 = self.parse_node(socket1) if socket1 else None
        socket2 = self.get_socket(blender_node, '', 2)
        shader2 = self.parse_node(socket2) if socket2 else None
        weight = self.get_value(blender_node, 'Fac')
        return self.blend_shader(shader1, shader2, weight)

    def parse_shader_node_diffuse(self, blender_node):
        log_mat('parse_shader_node_diffuse...')
        shader = DiffuseShader(self)
        color = self.get_value(blender_node, blender_node.color_in)
        log_mat("   diffuse_color: %s" % color)
        shader.set_color(color)
        roughness = self.get_value(blender_node, blender_node.roughness_in, default=1)
        log_mat("   diffuse_roughness: %s" % roughness)
        shader.set_roughness(roughness)
        socket = self.get_socket(blender_node, blender_node.normal_in)
        if socket is not None:
            shader.set_normal(self.parse_node(socket))
        return shader

    def parse_shader_node_subsurface(self, blender_node):
        log_mat('parse_shader_node_subsurface...')
        surface_intensity = self.get_value(blender_node, blender_node.surface_intensity_in)
        transparent_shader = TransparentShader(self)
        if surface_intensity.x <= 0:  # as float
            return transparent_shader

        socket = self.get_socket(blender_node, blender_node.color_in)
        if socket is None:
            color = self.get_value(blender_node, blender_node.color_in)
            shader = DiffuseShader(self)
            shader.set_color(color)
        else:
            shader = self.parse_node(socket)

        return self.blend_shader(transparent_shader, shader, surface_intensity)

    def parse_volume_node_subsurface(self, blender_node):
        log_mat('parse_volume_node_subsurface...')
        shader = VolumeShader(self)

        intensity = self.get_value(blender_node, blender_node.surface_intensity_in)
        if intensity.x > 0:
            shader.shader_blend = intensity

        subsurface_color = self.get_value(blender_node, blender_node.subsurface_color_in)
        density = self.get_value(blender_node, blender_node.density_in)
        scatter_color = self.get_value(blender_node, blender_node.scatter_color_in)
        scatter_amount = self.get_value(blender_node, blender_node.scatter_amount_in)
        emission_color = self.get_value(blender_node, blender_node.emission_color_in)
        scattering_direction = self.get_value(blender_node, blender_node.scattering_direction_in)
        multiscatter = self.get_value(blender_node, blender_node.multiscatter_in)
        sigmas = self.mul_value(self.mul_value(scatter_amount, density), scatter_color)
        shader.set_sigmas(sigmas)

        # absorption
        sigmaa = self.mul_value(self.sub_value(ValueVector(1, 1, 1, 1), subsurface_color), density)
        shader.set_sigmaa(sigmaa)

        # emission
        emission = self.mul_value(emission_color, density)
        shader.set_emission(emission)

        # phase and multi on/off
        shader.set_g(scattering_direction)
        shader.set_multiscatter(multiscatter)
        return shader

    def parse_volume_node_volume(self, blender_node):
        log_mat('parse_volume_node_volume...')
        shader = VolumeShader(self)

        transmission_color = self.get_value(blender_node, blender_node.transmission_color_in)
        density = self.get_value(blender_node, blender_node.density_in)
        scatter_color = self.get_value(blender_node, blender_node.scatter_color_in)
        emission_color = self.get_value(blender_node, blender_node.emission_color_in)
        scattering_direction = self.get_value(blender_node, blender_node.scattering_direction_in)
        multiscatter = self.get_value(blender_node, blender_node.multiscatter_in)

        # scattering
        sigmas = self.mul_value(density, scatter_color)
        shader.set_sigmas(sigmas)

        # absorption
        sigmaa = self.mul_value(self.sub_value(ValueVector(1, 1, 1, 1), transmission_color), density)
        shader.set_sigmaa(sigmaa)

        # emission
        emission = self.mul_value(emission_color, density)
        shader.set_emission(emission)

        # phase and multi on/off
        shader.set_g(scattering_direction)
        shader.set_multiscatter(multiscatter)
        return shader

    def parse_displacement_node(self, blender_node):
        log_mat('parse_displacement_node...')
        scale_min = blender_node.scale_min
        scale_max = blender_node.scale_max
        socket = self.get_socket(blender_node, blender_node.map_in)
        res = None

        logging.info('socket: ', socket)
        if socket:
            res = self.parse_node(socket)
        else:
            logging.warn("Displacement node hasn't map")

        if res and res.is_vector(): # error value
            logging.warn("Displacement map error")
            res = None
        return res, scale_min, scale_max


    def parse_shader_node_double_sided(self, blender_node):
        log_mat('parse_shader_node_double_sided...')
        shader = DoubleSidedShader(self)
        socket_front = self.get_socket(blender_node, blender_node.front_shader)
        if socket_front:
            shader.set_shader_front(self.parse_node(socket_front))
        socket_back = self.get_socket(blender_node, blender_node.back_shader)
        if socket_back:
            shader.set_shader_back(self.parse_node(socket_back))

        return shader

    def parse_shader_node_emissive(self, blender_node):
        log_mat('parse_shader_node_emissive...')
        shader = EmissiveShader(self)
        color = self.get_value(blender_node, blender_node.color_in)
        intensity = self.get_value(blender_node, blender_node.intensity_in)
        val = self.mul_value(color, intensity)
        shader.set_color(val)
        if blender_node.double_sided:
            emissive = shader
            shader = DoubleSidedShader(self)
            shader.set_shader_front(emissive)
            shader.set_shader_back(emissive)
        return shader

    def parse_shader_node_microfacet(self, blender_node):
        log_mat('parse_shader_node_microfacet...')
        shader = MicrofacetShader(self)
        color = self.get_value(blender_node, blender_node.color_in)
        roughness = self.get_value(blender_node, blender_node.roughness_in)
        socket = self.get_socket(blender_node, blender_node.normal_in)
        if socket:
            shader.set_normal(self.parse_node(socket))
        shader.set_color(color)
        shader.set_roughness(roughness)
        return shader

    def parse_shader_node_microfacet_refraction(self, blender_node):
        log_mat('parse_shader_node_microfacet_refraction...')
        shader = MicrofacetRefractionShader(self)
        color = self.get_value(blender_node, blender_node.color_in)
        roughness = self.get_value(blender_node, blender_node.roughness_in)
        ior = self.get_value(blender_node, blender_node.ior_in)

        socket = self.get_socket(blender_node, blender_node.normal_in)
        if socket:
            shader.set_normal(self.parse_node(socket))

        shader.set_color(color)
        shader.set_roughness(roughness)
        shader.set_ior(ior)
        return shader

    def parse_shader_node_blend(self, blender_node):
        log_mat('parse_shader_node_blend...')
        socket1 = self.get_socket(blender_node, blender_node.shader1_in)
        shader1 = self.parse_node(socket1) if socket1 else None

        socket2 = self.get_socket(blender_node, blender_node.shader2_in)
        shader2 = self.parse_node(socket2) if socket2 else None

        weight = self.get_value(blender_node, blender_node.weight_in)
        return self.blend_shader(shader1, shader2, weight)

    def get_socket(self, blender_node, name, index=None):
        if index is None:
            try:
                socket = blender_node.inputs[name]
            except KeyError:
                return None
        else:
            try:
                socket = blender_node.inputs[index]
            except IndexError:
                return None

        if socket.is_linked and len(socket.links) > 0:
            return socket.links[0].from_socket
        return None

    def parse_shader_node_output(self, blender_node):
        self.output_node_was_parsed = True

        # shader socket
        socket = self.get_socket(blender_node, blender_node.shader_in)
        if socket:
            shader = self.parse_node(socket)
        else:
            raise MaterialError("No RPR material node connected to shader socket in RPR Material Output node", blender_node)

        # volume socket
        socket = self.get_socket(blender_node, blender_node.volume_in)
        if socket:
            if socket.node.bl_idname in ['rpr_shader_node_volume', 'rpr_shader_node_subsurface']:
                volume = self.parse_node(socket)
                self.volume_handle = volume.get_handle()
                shader = self.prepare_surface_for_volume(shader, volume)
            else:
                raise MaterialError("RPR Volume or RPR Subsurface should be connected to output volume", blender_node)

        # displacement socket
        socket = self.get_socket(blender_node, blender_node.displacement_in)
        if socket:
            if socket.node.bl_idname == 'rpr_shader_node_displacement':
                self.displacement = self.parse_node(socket)
            else:
                raise MaterialError("RPR Displacement node should be connected to output displacement", blender_node)

        return shader

    def parse_shader_node_diffuse_refraction(self, blender_node):
        log_mat('parse_shader_node_diffuse_refraction...')
        shader = DiffuseRefractionShader(self)
        val = self.get_value(blender_node, blender_node.color_in)

        shader.set_color(val)

        socket = self.get_socket(blender_node, blender_node.normal_in)
        if socket:
            shader.set_normal(self.parse_node(socket))

        return shader

    def parse_shader_node_oren_nayar(self, blender_node):
        log_mat('parse_shader_node_oren_nayar...')
        color = self.get_value(blender_node, blender_node.color_in)
        roughness = self.get_value(blender_node, blender_node.roughness_in)
        shader = OrenNayarShader(self)
        shader.set_color(color)
        shader.set_roughness(roughness)

        socket = self.get_socket(blender_node, blender_node.normal_in)
        if socket:
            shader.set_normal(self.parse_node(socket))
        return shader

    def parse_shader_node_refraction(self, blender_node):
        log_mat('parse_shader_node_refraction...')
        color = self.get_value(blender_node, blender_node.color_in)
        ior = self.get_value(blender_node, blender_node.ior_in)
        shader = RefractionShader(self)
        shader.set_color(color)
        shader.set_ior(ior)
        socket = self.get_socket(blender_node, blender_node.normal_in)
        if socket:
            shader.set_normal(self.parse_node(socket))
        return shader

    def parse_shader_node_reflection(self, blender_node):
        log_mat('parse_shader_node_refraction...')
        shader = ReflectionShader(self)
        socket = self.get_socket(blender_node, blender_node.normal_in)
        if socket:
            shader.set_normal(self.parse_node(socket))
        shader.set_color(self.get_value(blender_node, blender_node.color_in))

        return shader

    def parse_shader_node_transparent(self, blender_node):
        log_mat('parse_shader_node_transparent...')
        color = self.get_value(blender_node, blender_node.color_in)
        shader = TransparentShader(self)
        shader.set_color(color)
        return shader

    def parse_shader_node_ward(self, blender_node):
        log_mat('parse_shader_node_ward...')
        color = self.get_value(blender_node, blender_node.color_in)
        rotation = self.get_value(blender_node, blender_node.rotation_in)
        roughness_x = self.get_value(blender_node, blender_node.roughness_x_in)
        roughness_y = self.get_value(blender_node, blender_node.roughness_y_in)
        shader = WardShader(self)
        shader.set_color(color)
        shader.set_rotation(rotation)
        shader.set_roughness_x(roughness_x)
        shader.set_roughness_y(roughness_y)
        socket = self.get_socket(blender_node, blender_node.normal_in)
        if socket:
            shader.set_normal(self.parse_node(socket))
        return shader

    def parse_shader_node_uber(self, blender_node):
        log_mat('parse_shader_node_uber...')

        shader = UberShader(self)

        # DIFFUSE BASE
        diffuse_color = self.get_value(blender_node, blender_node.diffuse_color_in)
        shader.set_diffuse_color(diffuse_color)
        socket = self.get_socket(blender_node, blender_node.diffuse_normal_in)
        if socket:
            shader.set_diffuse_normal(self.parse_node(socket))

        # GLOSSY REFLECTIONS
        if blender_node.reflection:
            reflect_color = self.get_value(blender_node, blender_node.reflect_color_in)
            reflect_ior = self.get_value(blender_node, blender_node.reflect_ior_in)
            reflect_roughness_x = self.get_value(blender_node, blender_node.reflect_roughness_x_in)
            reflect_roughness_y = self.get_value(blender_node, blender_node.reflect_roughness_y_in)

            f = 0.000001
            roughx = self.add_value(ValueVector(f, f, f, f), reflect_roughness_x)
            roughy = self.add_value(ValueVector(f, f, f, f), reflect_roughness_y)

            val_ior = ValueNode(FresnelNode(self, reflect_ior, Value(), Value()))

            shader.set_reflect_color(reflect_color)
            shader.set_reflect_ior(val_ior)
            shader.set_reflect_roughness_x(roughx)
            shader.set_reflect_roughness_y(roughy)

            socket = self.get_socket(blender_node, blender_node.reflect_normal_in)
            if socket:
                shader.set_reflect_normal(self.parse_node(socket))
        else:
            shader.set_reflect_ior(ValueVector())

        # CLEAR COAT
        if blender_node.clear_coat:
            coat_color = self.get_value(blender_node, blender_node.coat_color_in)
            coat_ior = self.get_value(blender_node, blender_node.coat_ior_in)

            val_ior = ValueNode(FresnelNode(self, coat_ior, Value(), Value()))

            shader.set_coat_color(coat_color)
            shader.set_coat_ior(val_ior)

            socket = self.get_socket(blender_node, blender_node.coat_normal_in)
            if socket:
                shader.set_coat_normal(self.parse_node(socket))
        else:
            shader.set_coat_ior(ValueVector())

        # REFRACTION
        if blender_node.refraction:
            refraction_level = self.get_value(blender_node, blender_node.refraction_level_in)
            val = self.sub_value(ValueVector(1, 1, 1, 1), refraction_level)
            refraction_color = self.get_value(blender_node, blender_node.refraction_color_in)
            refraction_ior = self.get_value(blender_node, blender_node.refraction_ior_in)
            refraction_roughness = self.get_value(blender_node, blender_node.refraction_roughness_in)

            shader.set_refraction(val)
            shader.set_refraction_color(refraction_color)
            shader.set_refraction_ior(refraction_ior)
            shader.set_refraction_roughness(refraction_roughness)

            socket = self.get_socket(blender_node, blender_node.refraction_normal_in)
            if socket:
                shader.set_refraction_normal(self.parse_node(socket))
        else:
            shader.set_refraction(ValueVector(1, 1, 1, 1))

        # TRANSPARENCY
        transparency_color = self.get_value(blender_node, blender_node.transparency_color_in)
        transparency_level = self.get_value(blender_node, blender_node.transparency_level_in)
        shader.set_transparency_color(transparency_color)
        shader.set_transparency_level(transparency_level)

        return shader


    def parse_shader_node_uber2(self, blender_node):
        log_mat('parse_shader_node_uber2...')

        shader = UberShader2(self)

        nul_value_vector = ValueVector(0,0,0,0)

        # DIFFUSE:
        if blender_node.diffuse:
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_DIFFUSE_COLOR,
                                  self.get_value(blender_node, blender_node.diffuse_color))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT,
                                  self.get_value(blender_node, blender_node.diffuse_weight))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS,
                                  self.get_value(blender_node, blender_node.diffuse_roughness))
        else:
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT,
                                  nul_value_vector)

        # REFLECTION:
        if blender_node.reflection:
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFLECTION_COLOR,
                                  self.get_value(blender_node, blender_node.reflection_color))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT,
                                  self.get_value(blender_node, blender_node.reflection_weight))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFLECTION_ROUGHNESS,
                                  self.get_value(blender_node, blender_node.reflection_roughness))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY,
                                  self.get_value(blender_node, blender_node.reflection_anisotropy))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY_ROTATION,
                                  self.get_value(blender_node, blender_node.reflection_anisotropy_rotation))

            if blender_node.reflection_fresnel_metalmaterial:
                # metallic material:
                shader.set_int_rprx(pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                                    pyrprx.UBER_MATERIAL_REFLECTION_MODE_METALNESS)
                shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFLECTION_METALNESS,
                                      self.get_value(blender_node, blender_node.reflection_fresnel_metalness))
            else:
                # PBR material
                shader.set_int_rprx(pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                                    pyrprx.UBER_MATERIAL_REFLECTION_MODE_PBR)
                shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFLECTION_IOR,
                                      self.get_value(blender_node, blender_node.reflection_fresnel_ior))
        else:
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT,
                                  nul_value_vector)

        # REFRACTION:
        if blender_node.refraction:
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFRACTION_COLOR,
                                  self.get_value(blender_node, blender_node.refraction_color))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT,
                                  self.get_value(blender_node, blender_node.refraction_weight))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFRACTION_ROUGHNESS,
                                  self.get_value(blender_node, blender_node.refraction_roughness))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFRACTION_IOR,
                                  self.get_value(blender_node, blender_node.refraction_ior))

            is_linked = blender_node.refraction_link_to_reflection
            is_thin_surface = blender_node.refraction_thin_surface

            # prevent crash in RPR (1.258) - "linked IOR" doesn't work when reflection mode set to "metallic"
            if blender_node.reflection_fresnel_metalmaterial:
                is_linked = False

            if pyrpr.API_VERSION < 0x010031000:
                shader.set_int_rprx(pyrprx.UBER_MATERIAL_REFRACTION_IOR_MODE,
                                    pyrprx.UBER_MATERIAL_REFRACTION_MODE_LINKED if is_linked else
                                    pyrprx.UBER_MATERIAL_REFRACTION_MODE_SEPARATE)

            shader.set_int_rprx(pyrprx.UBER_MATERIAL_REFRACTION_THIN_SURFACE,
                                pyrpr.TRUE if is_thin_surface else
                                pyrpr.FALSE)
        else:
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT,
                                  nul_value_vector)

        # COATING
        if blender_node.coating:
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_COATING_COLOR,
                                self.get_value(blender_node, blender_node.coating_color))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_COATING_WEIGHT,
                                self.get_value(blender_node, blender_node.coating_weight))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_COATING_ROUGHNESS,
                                self.get_value(blender_node, blender_node.coating_roughness))

            # PBR material:
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_COATING_IOR,
                                self.get_value(blender_node, blender_node.coating_fresnel_ior))
            shader.set_int_rprx(pyrprx.UBER_MATERIAL_COATING_MODE,
                                pyrprx.UBER_MATERIAL_COATING_MODE_PBR)
        else:
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_COATING_WEIGHT,
                                  nul_value_vector)

        # EMISSIVE:
        if blender_node.emissive:
            emissive_color = self.get_value(blender_node, blender_node.emissive_color)
            emissive_intesivity = self.get_value(blender_node, blender_node.emissive_intensity)
            val = self.mul_value(emissive_color, emissive_intesivity)

            shader.set_value_rprx(pyrprx.UBER_MATERIAL_EMISSION_COLOR, val)
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_EMISSION_WEIGHT,
                                self.get_value(blender_node, blender_node.emissive_weight))

            is_double_sided = blender_node.emissive_double_sided
            shader.set_int_rprx(pyrprx.UBER_MATERIAL_EMISSION_MODE,
                                pyrprx.UBER_MATERIAL_EMISSION_MODE_DOUBLESIDED if is_double_sided else
                                pyrprx.UBER_MATERIAL_EMISSION_MODE_SINGLESIDED)
        else:
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_EMISSION_WEIGHT,
                                  nul_value_vector)

        # SUBSURFACE
        if blender_node.subsurface:
            if pyrpr.API_VERSION < 0x010031000:
                use_diffuse_color = blender_node.subsurface_use_diffuse_color
                if use_diffuse_color and blender_node.diffuse:
                    shader.set_value_rprx(pyrprx.UBER_MATERIAL_SSS_SUBSURFACE_COLOR,
                                          self.get_value(blender_node, blender_node.diffuse_color))
                else:
                    shader.set_value_rprx(pyrprx.UBER_MATERIAL_SSS_SUBSURFACE_COLOR,
                                          self.get_value(blender_node, blender_node.subsurface_color))

            shader.set_value_rprx(pyrprx.UBER_MATERIAL_SSS_WEIGHT,
                                  self.get_value(blender_node, blender_node.subsurface_weight))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_SSS_SCATTER_COLOR,
                                  self.get_value(blender_node, blender_node.subsurface_scatter_color))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_SSS_SCATTER_DIRECTION,
                                  self.get_value(blender_node, blender_node.subsurface_scatter_direction))
            
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_SSS_SCATTER_DISTANCE, 
                                  self.get_value(blender_node, blender_node.subsurface_radius))

            shader.set_int_rprx(pyrprx.UBER_MATERIAL_SSS_MULTISCATTER,
                                pyrpr.TRUE if blender_node.subsurface_multiple_scattering else pyrpr.FALSE)
        else:
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_SSS_WEIGHT,
                                  nul_value_vector)

        # TRANSPARENCY
        if blender_node.transparency:
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_TRANSPARENCY,
                                  self.get_value(blender_node, blender_node.transparency_value))


        # NORMAL
        if blender_node.normal:
            normal_socket = self.get_socket(blender_node, blender_node.normal_in)
            if normal_socket is not None:
                if pyrpr.API_VERSION < 0x010031000:
                    shader.set_value_rprx(pyrprx.UBER_MATERIAL_NORMAL, self.parse_node(normal_socket))
                else:
                    shader.set_value_rprx(pyrprx.UBER_MATERIAL_DIFFUSE_NORMAL, self.parse_node(normal_socket))
                    shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFLECTION_NORMAL, self.parse_node(normal_socket))


        # DISPLACEMENT
        if blender_node.displacement:
            displacement_socket = self.get_socket(blender_node, blender_node.displacement_map)

            if type(displacement_socket) == bpy.types.NodeSocketShader:
                #displacement shader:
                #it's not handled,
                #use arithmetic nodes to change height
                logging.critical('Instead of Displacement Shader, Use Arithmetic Node to change Height!')
                assert(False)
            else:
                displacement_value = self.get_value(blender_node, blender_node.displacement_map)
                if not displacement_value.is_vector():
                    scale_min = self.get_value(blender_node, blender_node.displacement_min)
                    scale_max = self.get_value(blender_node, blender_node.displacement_max)
                    delta = self.sub_value(scale_max, scale_min)
                    displacement_value = self.mul_value(displacement_value, delta)
                    displacement_value = self.add_value(displacement_value, scale_min)
                    shader.set_value_rprx(pyrprx.UBER_MATERIAL_DISPLACEMENT, displacement_value)

        return shader

    def parse_shader_node_pbr(self, blender_node):
        log_mat('parse_shader_node_pbr...')

        shader = UberShader2(self)

        nul_value_vector = ValueVector(0,0,0,0)
        one_vector = ValueVector(1.0, 1.0, 1.0, 1.0)

        # DIFFUSE:
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_DIFFUSE_COLOR,
                                  self.get_value(blender_node, blender_node.base_color))
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT,
                              one_vector)
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS,
                                  self.get_value(blender_node, blender_node.roughness))
        
        # REFLECTION:
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFLECTION_COLOR,
                              self.get_value(blender_node, blender_node.base_color))
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT,
                              self.get_value(blender_node, blender_node.specular))
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFLECTION_ROUGHNESS,
                              self.get_value(blender_node, blender_node.roughness))
        shader.set_int_rprx(pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                            pyrprx.UBER_MATERIAL_REFLECTION_MODE_METALNESS)
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFLECTION_METALNESS,
                              self.get_value(blender_node, blender_node.metalness))
    
        # REFRACTION:
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFRACTION_COLOR,
                              self.get_value(blender_node, blender_node.base_color))
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT,
                              self.get_value(blender_node, blender_node.glass_weight))
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFRACTION_ROUGHNESS,
                              self.get_value(blender_node, blender_node.roughness))
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFRACTION_IOR,
                              self.get_value(blender_node, blender_node.glass_ior))
        shader.set_int_rprx(pyrprx.UBER_MATERIAL_REFRACTION_THIN_SURFACE,
                            pyrpr.FALSE)
        
        # SUBSURFACE
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_SSS_SUBSURFACE_COLOR,
                                  self.get_value(blender_node, blender_node.base_color))
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_SSS_WEIGHT,
                              self.get_value(blender_node, blender_node.sss_weight))
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_SSS_SCATTER_COLOR,
                              self.get_value(blender_node, blender_node.sss_color))
        shader.set_value_rprx(pyrprx.UBER_MATERIAL_SSS_SCATTER_DISTANCE, 
                              self.get_value(blender_node, blender_node.sss_radius))
        shader.set_int_rprx(pyrprx.UBER_MATERIAL_SSS_MULTISCATTER,
                            pyrpr.FALSE)

        # EMISSION
        emissive_weight = self.get_value(blender_node, blender_node.emissive_weight)
        if emissive_weight != nul_value_vector:
            emissive_color = self.get_value(blender_node, blender_node.emissive_color)
            emissive_intensity = self.get_value(blender_node, blender_node.emissive_intensity)
            val = self.mul_value(emissive_color, emissive_intensity)

            shader.set_value_rprx(pyrprx.UBER_MATERIAL_EMISSION_COLOR, val)
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_EMISSION_WEIGHT, emissive_weight)
            shader.set_int_rprx(pyrprx.UBER_MATERIAL_EMISSION_MODE, pyrprx.UBER_MATERIAL_EMISSION_MODE_SINGLESIDED)
        else:
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_EMISSION_WEIGHT, nul_value_vector)

        # NORMAL
        normal_socket = self.get_socket(blender_node, blender_node.normal_in)
        if normal_socket is not None:
            if pyrpr.API_VERSION < 0x010031000:
                shader.set_value_rprx(pyrprx.UBER_MATERIAL_NORMAL, self.parse_node(normal_socket))
            else:
                shader.set_value_rprx(pyrprx.UBER_MATERIAL_DIFFUSE_NORMAL, self.parse_node(normal_socket))
                shader.set_value_rprx(pyrprx.UBER_MATERIAL_REFLECTION_NORMAL, self.parse_node(normal_socket))

        return shader


    def parse_input_node_constant(self, blender_node):
        log_mat('parse_input_node_constant...')
        color = blender_node.color
        return ValueVector(color[0], color[1], color[2], color[3])

    def parse_input_node_value(self, blender_node):
        log_mat('parse_input_node_value...')
        val = blender_node.default_value
        return ValueVector(val[0], val[1], val[2], val[3])

    def parse_node_normalmap(self, blender_node):
        log_mat('parse_node_normalmap...')
        node = NormalMapNode(self)
        socket = self.get_socket(blender_node, blender_node.map_in)
        if not socket:
            return Value()

        map_value = self.parse_node(socket)
        if blender_node.flip_x or blender_node.flip_y:
            # For flip_x the calculation is following: final_x = 1-x
            # therefore for vector map_value it would be: map_value = (1,0,0,0) + (-1,1,1,1)*map_value
            # The same calculation for Y coordinate
            mul_vector = ValueVector(-1 if blender_node.flip_x else 1,
                                     -1 if blender_node.flip_y else 1,
                                     1, 1)
            add_vector = ValueVector(1 if blender_node.flip_x else 0,
                                     1 if blender_node.flip_y else 0,
                                     0, 0)
            map_value = self.add_value(self.mul_value(map_value, mul_vector), 
                                     add_vector)

        node.set_map(map_value)
        node.set_value(b'bumpscale', self.get_value(blender_node, blender_node.scale_in))
        return ValueNode(node)

    def parse_node_bumpmap(self, blender_node):
        log_mat('parse_node_bumpmap...')
        node = BumpMapNode(self)
        socket = self.get_socket(blender_node, blender_node.map_in)
        if not socket:
            return Value()

        node.set_map(self.parse_node(socket))
        node.set_bumpscale(self.get_value(blender_node, blender_node.scale_in))
        return ValueNode(node)

    def parse_texture_node_image_map(self, blender_node):
        image = self.parse_texture_node_get_image(blender_node)

        if not image:
            return self.create_error_value()

        node = ImageTextureNode(self)
        node.set_map(image)

        uv = self.get_mapping(blender_node)
        node.set_uv(uv)
        return ValueNode(node)

    def parse_color_ramp_node(self, blender_node):
        context = self.manager.get_core_context()
        core_buffer = buffer.create_core_buffer_from_color_ramp(context, blender_node.color_ramp)
        self.node_list.append(core_buffer)
        node = BufferSamplerShader(self, self.get_value(blender_node, 'Fac'), core_buffer)
        return ValueNode(node)


    def parse_ao_map(self, blender_node):
        log_mat('parse_node_ao_map...')
        side = ValueVector(1.0, 0.0, 0.0, 0.0) if blender_node.side == 'FRONT' else ValueVector(-1.0, 0.0, 0.0, 0.0)
        radius = ValueVector(blender_node.radius, 0.0, 0.0, 0.0)
        node = AOMapShader(self, radius, side)
        
        return self.blend_value(self.get_value(blender_node, blender_node.occluded_color), 
                                self.get_value(blender_node, blender_node.unoccluded_color), 
                                ValueNode(node))

    def parse_texture_node_get_image(self, blender_node):
        img = blender_node.get_image()
        if not img:
            log_mat("parse_texture_node_get_image : image is empty")
            return None

        return self.parse_image(img, blender_node.color_space_type, blender_node.wrap_type)

    def parse_image(self, source_image, color_space_type, wrap_type=None):
        log_mat('Parse : image map "%s"...' % source_image.filepath)
        context = self.manager.get_core_context()
        image = Image(rprblender.core.image.get_core_image_for_blender_image(context, source_image))
        if color_space_type == 'sRGB':
            pyrpr.ImageSetGamma(image.get_handle(), 2.2)
        else:
            pyrpr.ImageSetGamma(image.get_handle(), 1)

        if wrap_type:
            wrap_type = 'IMAGE_WRAP_TYPE_' + wrap_type
            pyrpr.ImageSetWrap(image.get_handle(), getattr(pyrpr, wrap_type))

        self.node_list.append(image.handle)
        return ValueImage(image)

    def parse_cycles_TexImage(self, blender_node):
        if not blender_node.image:
            log_mat('parse_cycles_TexImage - image is empty.')
            return ValueVector(1, 1, 1, 1)

        image = self.parse_image(blender_node.image, blender_node.color_space_type)
        node = ImageTextureNode(self)
        node.set_map(image)
        return ValueNode(node)

    def parse_cycles_RGBCurve(self, blender_node):
        log_mat('parse_cycles_RGBCurve...')
        socket = self.get_socket(blender_node, 'Color')
        res = self.parse_node(socket) if socket else Value()
        return res

    def parse_cycles_HueSaturation(self, blender_node):
        log_mat('parse_cycles_HueSaturation...')
        socket = self.get_socket(blender_node, 'Color')
        res = self.parse_node(socket) if socket else Value()
        return res

    def parse_cycles_MixRGB(self, blender_node):
        log_mat('parse_cycles_MixRGB...')
        a = self.get_value(blender_node, 'Color1')
        b = self.get_value(blender_node, 'Color2')
        weight = self.get_value(blender_node, 'Fac')
        return self.blend_value(a, b, weight)

    def parse_node_noise2d(self, blender_node):
        log_mat('parse_node_noise2d...')
        uv = self.get_mapping(blender_node)
        node = Noise2DTextureNode(self, uv)
        return ValueNode(node)

    def parse_node_gradient(self, blender_node):
        log_mat('parse_node_gradient...')
        color1 = self.get_value(blender_node, blender_node.color1_in)
        color2 = self.get_value(blender_node, blender_node.color2_in)
        uv = self.get_mapping(blender_node)
        node = GradientTextureNode(self, color1, color2, uv)
        return ValueNode(node)

    def parse_node_checker(self, blender_node):
        log_mat('parse_node_checker...')
        uv = self.get_mapping(blender_node)
        node = CheckerTextureNode(self, uv)
        return ValueNode(node)

    def parse_texture_node_dot(self, blender_node):
        log_mat('parse_texture_node_dot...')
        uv = self.get_mapping(blender_node)
        node = DotTextureNode(self, uv)
        return ValueNode(node)

    def parse_fresnel_schlick_node(self, blender_node):
        log_mat('parse_fresnel_schlick_node...')
        reflectance = self.get_value(blender_node, blender_node.reflectance_in)
        socket = self.get_socket(blender_node, blender_node.normal_in)
        normal = self.parse_node(socket) if socket else Value()
        socket = self.get_socket(blender_node, blender_node.in_vec_in)
        in_vec = self.parse_node(socket) if socket else Value()
        node = FresnelSchlickNode(self, reflectance, normal, in_vec)
        return ValueNode(node)

    def parse_fresnel_node(self, blender_node):
        log_mat('parse_fresnel_node...')
        ior = self.get_value(blender_node, blender_node.ior_in)
        socket = self.get_socket(blender_node, blender_node.normal_in)
        normal = self.parse_node(socket) if socket else Value()
        socket = self.get_socket(blender_node, blender_node.in_vec_in)
        in_vec = self.parse_node(socket) if socket else Value()
        node = FresnelNode(self, ior, normal, in_vec)
        return ValueNode(node)

    def parse_mapping_node(self, blender_node):
        log_mat('parse_mapping_node...')
        node = LookupNode(self, LookupType.uv)
        res = ValueNode(node)
        scale = self.get_value(blender_node, blender_node.scale_in)
        if scale.is_vector() and (scale.x != 1.0 or scale.y != 1.0):
            res = self.mul_value(res, scale)
        offset = self.get_value(blender_node, blender_node.offset_in)
        if offset.is_vector() and (offset.x != 0.0 or offset.y != 0.0):
            res = self.add_value(res, offset)
        return res

    def parse_input_node_lookup(self, blender_node):
        log_mat('parse_lookup_node...')
        node = LookupNode(self, getattr(pyrpr, 'MATERIAL_NODE_LOOKUP_' + blender_node.type))
        return ValueNode(node)

    def parse_node_reroute(self, blender_node):
        log_mat('parse_node_reroute...')

        node_name = blender_node.name
        value = blender_node.as_pointer()
        node_id = node_name + "_" + str(hash(value))

        if node_id in self.reroute_list:
            log_mat('reroute %s found in list' % node_id)
            return self.reroute_list[node_id]

        next_socket = self.get_socket(blender_node, '', 0)
        if not next_socket:
            log_mat("Reroute hasn't input node")
            return self.create_error_value()

        val = self.parse_node(next_socket)
        self.reroute_list[node_id] = val
        return val

    def parse_arithmetics_node_value_blend(self, blender_node):
        log_mat('parse_arithmetics_node_value_blend...')
        a = self.get_value(blender_node, blender_node.value1_in)
        b = self.get_value(blender_node, blender_node.value2_in)
        weight = self.get_value(blender_node, blender_node.weight_in)
        return self.blend_value(a, b, weight)

    def parse_arithmetics_node_math(self, blender_node):
        log_mat('parse_arithmetics_node_math...')
        op = blender_node.op
        log_mat('   math operation(%s)' % op)
        a = self.get_value(blender_node, 0)
        b = self.get_value(blender_node, 1)
        c = self.get_value(blender_node, 2)

        val = None
        if op == 'ADD':
            val = self.add_value(a, b)
        elif op == 'SUB':
            val = self.sub_value(a, b)
        elif op == 'MUL':
            val = self.mul_value(a, b)
        elif op == 'SIN':
            val = self.sin_value(a)
        elif op == 'COS':
            val = self.cos_value(a)
        elif op == 'TAN':
            val = self.tan_value(a)
        elif op == 'ASIN':
            val = self.asin_value(a)
        elif op == 'ACOS':
            val = self.acos_value(a)
        elif op == 'ATAN':
            val = self.atan_value(a)
        elif op == 'DOT3':
            val = self.dot3_value(a, b)
        elif op == 'DOT4':
            val = self.dot4_value(a, b)
        elif op == 'CROSS3':
            val = self.cross_value(a, b)
        elif op == 'LENGTH3':
            val = self.length3_value(a)
        elif op == 'NORMALIZE3':
            val = self.normalize_value(a)
        elif op == 'POW':
            val = self.pow_value(a, b)
        elif op == 'MIN':
            val = self.min_value(a, b)
        elif op == 'MAX':
            val = self.max_value(a, b)
        elif op == 'FLOOR':
            val = self.floor_value(a)
        elif op == 'MOD':
            val = self.mod_value(a, b)
        elif op == 'ABS':
            val = self.abs_value(a)
        elif op == 'SELECT_X':
            val = self.select_x_value(a)
        elif op == 'SELECT_Y':
            val = self.select_y_value(a)
        elif op == 'SELECT_Z':
            val = self.select_z_value(a)
        elif op == 'SELECT_W':
            val = self.select_w_value(a)
        elif op == 'COMBINE':
            val = self.combine_value(a, b, c)
        elif op == 'AVERAGE_XYZ':
            val = self.average_xyz_value(a)
        elif op == 'AVERAGE':
            val = self.average_value(a, b)
        elif op == 'DIV':
            val = self.div_value(a, b)
        else:
            val = Value()
            log_mat('parse_arithmetics_node_value_blend : unknown operator type (%s)' % op)

        if blender_node.use_clamp:
            log_mat('   use_clamp: True')
            val = self.min_value(val, ValueVector(1, 1, 1, 1))
            val = self.max_value(val, ValueVector(0, 0, 0, 0))

        return val

    def create_material_node(self, matType):
        core_node = pyrpr.MaterialNode()
        pyrpr.MaterialSystemCreateNode(self.manager.get_material_system(), matType, core_node)
        self.node_list.append(core_node)
        return core_node

    def create_uber_material(self):
        uber_material = pyrprx.Object('rprx_material')
        pyrprx.CreateMaterial(self.manager.get_uber_rprx_context(), pyrprx.MATERIAL_UBER, uber_material)
        self.node_list.append(uber_material)
        return uber_material

    def blend_shader(self, shader1, shader2, weight):
        log_mat("blend_shader : %s, %s" % (shader1, shader2))

        if shader1 is None and shader2 is None:
            raise MaterialError("RPR material nodes should be connected to shader_1 or shader_2 sockets in RPR Blend node", self)
        if shader1 is None:
            return shader2
        if shader2 is None:
            return shader1

        if weight.is_vector():
            log_mat("blend_shader weight: ", weight.x)
            if weight.x <= 0:
                return shader1
            if weight.x >= 1:
                return shader2

        shader = BlendShader(self)
        shader.set_shader1(shader1)
        shader.set_shader2(shader2)
        shader.set_weight(weight)
        return shader

    def get_value(self, blender_node, name, default=None):
        try:
            socket = blender_node.inputs[name]
        except KeyError:
            if default:
                return ValueVector(*(default,) * 4)
            else:
                return Value()
        if socket.is_linked and len(socket.links) > 0:
            log_mat("get_value : from  linked node (socket: %s)" % socket, blender_node, name)
            linked_socket = socket.links[0].from_socket
            return self.parse_node(linked_socket)
        else:
            log_mat("get_value : from socket (socket: %s)" % socket, blender_node, name)
            if hasattr(socket, 'default_value'):
                value = socket.default_value
                if isinstance(value, bool):
                    log_mat("bool value")
                    value = 1.0 if value else 0.0
                    val = ValueVector(value, value, value, value)
                elif isinstance(value, float):
                    log_mat("float value")
                    val = ValueVector(value, value, value, value)
                elif len(value) == 4:
                    log_mat("vector4 value")
                    val = ValueVector(value[0], value[1], value[2], value[3])
                elif len(value) == 3:
                    log_mat("vector3 value")
                    val = ValueVector(value[0], value[1], value[2], 1.0)
                elif len(value) == 2:
                    log_mat("vector2 value")
                    val = ValueVector(value[0], value[1], 0, 1.0)
                else:
                    log_mat("unknown value type")
                    val = ValueVector()
            else:
                val = Value()
                log_mat("get_value : value (%s) hasn't default value and wasn't linked" % name)

            return val

    ####################################################################################################################

    def get_start_node(self, blender_mat):
        # look for output node in groups (like cycles)
        blender_node, group_node_list = rprblender.node_editor.find_output_node_in_group(blender_mat)
        if blender_node:
            log_mat('get_start_node: group_node_list: ', list(group_node_list))
            for node in group_node_list:
                self.store_node_group_in_list(node)

            return blender_node

        return None

    def store_node_group_in_list(self, blender_node):
        log_mat('store_node_group_in_list: Store return node: ', blender_node.bl_idname)
        # store return point

        tree = get_node_groups_by_id(blender_node.bl_idname)
        if not tree:
            logging.warn('store_node_group_in_list : Node group not found: ', blender_node.bl_idname)
            return

        input_node = tree.nodes.get("Group Inputs")
        node_id = input_node.name + "_" + str(hash(input_node.as_pointer()))
        self.node_groups_list[node_id] = blender_node

    def set_error(self, *args):
        logging.warn(args, tag='material')
        self.has_error = True

    def parse(self, blender_mat):
        log_mat("parse : " + blender_mat.name)
        self.name = blender_mat.name
        self.output_node_was_parsed = False
        self.node_group_stack = []
        blender_node = self.get_start_node(blender_mat)
        if not blender_node:
            # here we log only warning, no need to call set_error()
            logging.warn("Parse : Can't get output node, return error shader (material: %s)" % blender_mat.name, tag='material')
            return

        try:
            self.shader = self.parse_root_node(blender_node)
        except MaterialError as e:
            logging.debug(traceback.format_exc(), tag='material')
            self.set_error("Failed to parse material '{}' with node '{}'. {}".format(blender_mat.name, blender_node.name, e))
            self.shader = self.create_error_shader()

    def parse_root_node(self, blender_node):
        return self.parse_node(None, blender_node)

    def get_socket_index(self, sockets_list, socket):
        for i, s in enumerate(sockets_list):
            if s == socket:
                return i

    # blender_node - used for start parsing only
    def parse_node(self, socket, blender_node=None):
        if socket and blender_node is None:
            blender_node = socket.node

        assert blender_node
        log_mat('Parse node: %s, socket: %s' % (blender_node.bl_idname, socket.name if socket else 'None'))

        name = blender_node.bl_idname
        registered_nodes = {
            'rpr_shader_node_output': self.parse_shader_node_output,
            'rpr_shader_node_diffuse': self.parse_shader_node_diffuse,
            'rpr_shader_node_double_sided': self.parse_shader_node_double_sided,
            'rpr_shader_node_emissive': self.parse_shader_node_emissive,
            'rpr_shader_node_microfacet': self.parse_shader_node_microfacet,
            'rpr_shader_node_microfacet_refraction': self.parse_shader_node_microfacet_refraction,
            'rpr_shader_node_blend': self.parse_shader_node_blend,
            'rpr_shader_node_diffuse_refraction': self.parse_shader_node_diffuse_refraction,
            'rpr_shader_node_oren_nayar': self.parse_shader_node_oren_nayar,
            'rpr_shader_node_refraction': self.parse_shader_node_refraction,
            'rpr_shader_node_reflection': self.parse_shader_node_reflection,
            'rpr_shader_node_transparent': self.parse_shader_node_transparent,
            'rpr_shader_node_ward': self.parse_shader_node_ward,
            'rpr_shader_node_uber': self.parse_shader_node_uber,
            'rpr_shader_node_uber2': self.parse_shader_node_uber2,
            'rpr_shader_node_pbr': self.parse_shader_node_pbr,

            'rpr_texture_node_image_map': self.parse_texture_node_image_map,
            'rpr_mapping_node': self.parse_mapping_node,
            'rpr_arithmetics_node_value_blend': self.parse_arithmetics_node_value_blend,
            'rpr_arithmetics_node_math': self.parse_arithmetics_node_math,
            'rpr_input_node_constant': self.parse_input_node_constant,
            'rpr_input_node_value': self.parse_input_node_value,
            'rpr_input_node_lookup': self.parse_input_node_lookup,
            'rpr_input_node_normalmap': self.parse_node_normalmap,
            'rpr_input_node_bumpmap': self.parse_node_bumpmap,
            'rpr_texture_node_noise2d': self.parse_node_noise2d,
            'rpr_texture_node_gradient': self.parse_node_gradient,
            'rpr_texture_node_checker': self.parse_node_checker,
            'rpr_texture_node_dot': self.parse_texture_node_dot,
            'rpr_fresnel_schlick_node': self.parse_fresnel_schlick_node,
            'rpr_fresnel_node': self.parse_fresnel_node,
            'rpr_texture_node_ao': self.parse_ao_map,
            'ShaderNodeValToRGB': self.parse_color_ramp_node,

            # volume
            'rpr_shader_node_subsurface': self.parse_volume_node_subsurface,
            'rpr_shader_node_volume': self.parse_volume_node_volume,

            # displacement
            'rpr_shader_node_displacement': self.parse_displacement_node,

            # blender nodes
            'NodeReroute': self.parse_node_reroute,

            # cycles nodes
            'ShaderNodeOutputMaterial': self.parse_cycles_shader_OutputMaterial,
            'ShaderNodeBsdfDiffuse': self.parse_cycles_shader_node_BsdfDiffuse,
            'ShaderNodeMixShader': self.parse_cycles_shader_node_MixShader,
            'ShaderNodeTexImage': self.parse_cycles_TexImage,
            'ShaderNodeRGBCurve': self.parse_cycles_RGBCurve,
            'ShaderNodeHueSaturation': self.parse_cycles_HueSaturation,
            'ShaderNodeMixRGB': self.parse_cycles_MixRGB,

        }
        if name in registered_nodes:
            return registered_nodes[name](blender_node)
        elif name == 'rpr_shader_node_group_input':
            # parse group input
            node_id = blender_node.name + "_" + str(hash(blender_node.as_pointer()))
            log_mat('self.node_groups_list: ', list(self.node_groups_list))
            node_group = self.node_groups_list[node_id]

            log_mat('socket: ', socket)
            log_mat('blender_node.outputs: ', blender_node.outputs)
            socket_index = self.get_socket_index(blender_node.outputs, socket)
            if node_group.inputs[socket_index].is_linked:
                socket_out = node_group.inputs[socket_index].links[0].from_socket
                return self.parse_node(socket_out)
            else:
                # return value
                socket_in_group_node = node_group.inputs[socket_index]
                if hasattr(socket_in_group_node, 'default_value'):
                    value = socket_in_group_node.default_value
                    if isinstance(value, bool):
                        log_mat("bool value")
                        value = 1.0 if value else 0.0
                        val = ValueVector(value, value, value, value)
                    elif isinstance(value, float):
                        log_mat("float value")
                        val = ValueVector(value, value, value, value)
                    elif len(value) == 4:
                        log_mat("vector4 value")
                        val = ValueVector(value[0], value[1], value[2], value[3])
                    elif len(value) == 3:
                        log_mat("vector3 value")
                        val = ValueVector(value[0], value[1], value[2], 1.0)
                    elif len(value) == 2:
                        log_mat("vector2 value")
                        val = ValueVector(value[0], value[1], 0, 1.0)
                    else:
                        log_mat("unknown value type")
                        val = ValueVector()
                else:
                    val = Value()

                return val
        else:
            # parse group
            log_mat('parse node groups: ' + blender_node.bl_idname)
            tree = get_node_groups_by_id(blender_node.bl_idname)
            if tree:
                nodes = tree.nodes

                # store return point
                self.store_node_group_in_list(blender_node)

                # if group contain output node
                if not self.output_node_was_parsed:
                    output_node = rprblender.node_editor.find_output_node_in_tree(tree)
                    return self.parse_node(None, output_node)

                output_node = nodes.get("Group Outputs")
                log_mat('output_node: ', output_node)

                socket_index = self.get_socket_index(blender_node.outputs, socket)
                socket_out = output_node.inputs[socket_index].links[0].from_socket
                return self.parse_node(socket_out)

        message = "Error: we haven't implementation for node: " + blender_node.bl_idname

        if not self.output_node_was_parsed:
            converter = rprblender.converter.cycles_converter.CyclesMaterialConverter()
            cycles_nodes_support = converter.get_convert_func_library()
            if blender_node.bl_idname in cycles_nodes_support:
                message = blender_node.bl_idname + " could not be automatically translated, please use 'RPR Converter' panel to convert Cycles material to RPR"

        logging.warn(message)
        assert False, message

    def prepare_surface_for_volume(self, shader, volume):
        log_mat('prepare_surface_for_volume...')
        transparent_shader = TransparentShader(self)
        if hasattr(volume, 'shader_blend'):
            return self.blend_shader(transparent_shader, shader, volume.shader_blend)
        return transparent_shader

    ########################################################################################################################
    # Maths
    ########################################################################################################################

    def blend_value(self, a, b, weight):
        log_mat("blend_value : %s, %s" % (a, b))

        if weight.is_vector():
            k = weight.x
            log_mat("blend_value weight: ", k)
            if k <= 0:
                return a
            if k >= 1:
                return b
            if a.is_vector() and b.is_vector():
                return ValueVector(a.x * (1 - k) + b.x * k,
                                   a.y * (1 - k) + b.y * k,
                                   a.z * (1 - k) + b.z * k,
                                   a.w * (1 - k) + b.w * k)

        log_mat("blend_value : add blend node...")
        node = BlendNode(self, a, b, weight)
        return ValueNode(node)

    def core_trigonometry_func(self, a, func, op):
        log_mat("core_trigonometry_func: ", op)
        if a.is_vector():
            return ValueVector(func(a.x), func(a.y), func(a.z), func(a.w))
        log_mat("core_trigonometry_func : add arithmetic node...")
        node = ArithmeticNode(self, a, None, op)
        return ValueNode(node)

    def sin_value(self, a):
        log_mat("sin_value")
        return self.core_trigonometry_func(a, math.sin, OperatorType.SIN)

    def cos_value(self, a):
        log_mat("cos_value")
        return self.core_trigonometry_func(a, math.cos, OperatorType.COS)

    def tan_value(self, a):
        log_mat("tan_value")
        return self.core_trigonometry_func(a, math.tan, OperatorType.TAN)

    def acos_value(self, a):
        log_mat("acos_value")
        if a.is_vector():
            a = ValueVector(unit_clamp(a.x), unit_clamp(a.y), unit_clamp(a.z), unit_clamp(a.w))
        return self.core_trigonometry_func(a, math.acos, OperatorType.ACOS)

    def asin_value(self, a):
        log_mat("asin_value")
        if a.is_vector():
            a = ValueVector(unit_clamp(a.x), unit_clamp(a.y), unit_clamp(a.z), unit_clamp(a.w))
        return self.core_trigonometry_func(a, math.asin, OperatorType.ASIN)

    def atan_value(self, a):
        log_mat("atan_value")
        return self.core_trigonometry_func(a, math.atan, OperatorType.ATAN)

    def dot3_value(self, a, b):
        log_mat("dot3_value")
        if a.is_vector() and b.is_vector():
            d = a.x * b.x + a.y * b.y + a.z * b.z;
            return ValueVector(d, d, d, d)
        log_mat("dot3_value : add arithmetic node...")
        node = ArithmeticNode(self, a, b, OperatorType.DOT3)
        return ValueNode(node)

    def dot4_value(self, a, b):
        log_mat("dot4_value", a, b)
        if a.is_vector() and b.is_vector():
            d = a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w;
            return ValueVector(d, d, d, d)
        log_mat("dot4_value : add arithmetic node...")
        node = ArithmeticNode(self, a, b, OperatorType.DOT4)
        return ValueNode(node)

    def cross_value(self, a, b):
        log_mat("cross_value : add arithmetic node...")
        node = ArithmeticNode(self, a, b, OperatorType.CROSS3)
        return ValueNode(node)

    def length3_value(self, a):
        log_mat("length3_value")
        if a.is_vector():
            l = math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z)
            return ValueVector(l, l, l, l)
        log_mat("length3_value : add arithmetic node...")
        node = ArithmeticNode(self, a, None, OperatorType.LENGTH3)
        return ValueNode(node)

    def normalize_value(self, a):
        log_mat("normalize_value")
        if a.is_vector():
            l = math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z + a.w * a.w);
            if l > 0:
                l = 1.0 / l
            return ValueVector(a.x * l + a.y * l + a.z * l + a.w * l)
        log_mat("normalize_value : add arithmetic node...")
        node = ArithmeticNode(self, a, None, OperatorType.NORMALIZE3)
        return ValueNode(node)

    def pow_value(self, a, b):
        log_mat("pow_value")
        if a.is_vector() and b.is_vector():
            return ValueVector(math.pow(a.x, b.x), math.pow(a.y, b.y), math.pow(a.z, b.z), math.pow(a.w, b.w))
        log_mat("pow_value : add arithmetic node...")
        node = ArithmeticNode(self, a, b, OperatorType.POW)
        return ValueNode(node)

    def min_value(self, a, b):
        log_mat("min_value")
        if a.is_vector() and b.is_vector():
            return ValueVector(min(a.x, b.x), min(a.y, b.y), min(a.z, b.z), min(a.w, b.w))
        log_mat("min_value : add arithmetic node...")
        node = ArithmeticNode(self, a, b, OperatorType.MIN)
        return ValueNode(node)

    def max_value(self, a, b):
        log_mat("max_value")
        if a.is_vector() and b.is_vector():
            return ValueVector(max(a.x, b.x), max(a.y, b.y), max(a.z, b.z), max(a.w, b.w))
        log_mat("max_value : add arithmetic node...")
        node = ArithmeticNode(self, a, b, OperatorType.MAX)
        return ValueNode(node)

    def floor_value(self, a):
        log_mat("floor_value")
        if a.is_vector():
            return ValueVector(math.floor(a.x), math.floor(a.y), math.floor(a.z), math.floor(a.w))
        log_mat("floor_value : add arithmetic node...")
        node = ArithmeticNode(self, a, None, OperatorType.FLOOR)
        return ValueNode(node)

    def mod_value(self, a, b):
        log_mat("mod_value")
        if a.is_vector() and b.is_vector():
            return ValueVector(safe_mod(a.x, b.x), safe_mod(a.y, b.y), safe_mod(a.z, b.z), safe_mod(a.w, b.w))
        log_mat("mod_value : add arithmetic node...")
        node = ArithmeticNode(self, a, b, OperatorType.MOD)
        return ValueNode(node)

    def abs_value(self, a):
        log_mat("abs_value")
        if a.is_vector():
            return ValueVector(math.fabs(a.x), math.fabs(a.y), math.fabs(a.z), math.fabs(a.w))
        log_mat("abs_value : add arithmetic node...")
        node = ArithmeticNode(self, a, None, OperatorType.ABS)
        return ValueNode(node)

    def select_x_value(self, a):
        log_mat("select_x_value")
        if a.is_vector():
            return ValueVector(a.x, a.x, a.x, a.x)
        log_mat("select_x_value : add arithmetic node...")
        node = ArithmeticNode(self, a, None, OperatorType.SELECT_X)
        return ValueNode(node)

    def select_y_value(self, a):
        log_mat("select_y_value")
        if a.is_vector():
            return ValueVector(a.y, a.y, a.y, a.y)
        log_mat("select_y_value : add arithmetic node...")
        node = ArithmeticNode(self, a, None, OperatorType.SELECT_Y)
        return ValueNode(node)

    def select_z_value(self, a):
        log_mat("select_z_value")
        if a.is_vector():
            return ValueVector(a.z, a.z, a.z, a.z)
        log_mat("select_z_value : add arithmetic node...")
        node = ArithmeticNode(self, a, None, OperatorType.SELECT_Z)
        return ValueNode(node)

    def select_w_value(self, a):
        log_mat("select_w_value")
        if a.is_vector():
            return ValueVector(a.w, a.w, a.w, a.w)
        log_mat("select_w_value : add arithmetic node...")
        node = ArithmeticNode(self, a, None, OperatorType.SELECT_W)
        return ValueNode(node)

    def combine_value(self, a, b, c):
        log_mat("combine_value")
        if a.is_vector() and b.is_vector() and c.is_vector():
            return ValueVector(a.x, b.y, c.z, 0)
        log_mat("combine_value : add arithmetic node...")

        vX = self.mul_value(a, ValueVector(1, 0, 0))
        vY = self.mul_value(b, ValueVector(0, 1, 0))
        vZ = self.mul_value(c, ValueVector(0, 0, 1))

        res = self.add_value(self.add_value(vX, vY), vZ)
        return res

    def average_xyz_value(self, a):
        log_mat("average_xyz_value")
        if a.is_vector():
            avr = (a.x + a.y + a.z) / 3.0
            return ValueVector(avr, avr, avr, avr)
        log_mat("average_xyz_value : add arithmetic node...")
        node = ArithmeticNode(self, a, None, OperatorType.AVERAGE_XYZ)
        return ValueNode(node)

    def average_value(self, a, b):
        log_mat("average_value")
        if a.is_vector():
            return ValueVector((a.x + b.x) * 0.5, (a.y + b.y) * 0.5, (a.z + b.z) * 0.5, (a.w + b.w) * 0.5)
        log_mat("average_value : add arithmetic node...")
        node = ArithmeticNode(self, a, b, OperatorType.AVERAGE)
        return ValueNode(node)

    def mul_value(self, a, b):
        log_mat("mul_value")
        if a.is_vector() and b.is_vector():
            return ValueVector(a.x * b.x, a.y * b.y, a.z * b.z, a.w * b.w)
        log_mat("mul_value : add arithmetic node...")
        node = ArithmeticNode(self, a, b, OperatorType.MUL)
        return ValueNode(node)

    def div_value(self, a, b):
        log_mat("div_value")
        if a.is_vector() and b.is_vector():
            return ValueVector(
                self.div_safe(a.x, b.x),
                self.div_safe(a.y, b.y),
                self.div_safe(a.z, b.z),
                self.div_safe(a.w, b.w))
        log_mat("div_value : add arithmetic node...")
        node = ArithmeticNode(self, a, b, OperatorType.DIV)
        return ValueNode(node)

    def div_safe(self, a, b):
        return a / b if b else 0

    def add_value(self, a, b):
        log_mat("add_value")
        if a.is_vector() and b.is_vector():
            return ValueVector(a.x + b.x, a.y + b.y, a.z + b.z, a.w + b.w)
        log_mat("add_value : add arithmetic node...")
        node = ArithmeticNode(self, a, b, OperatorType.ADD)
        return ValueNode(node)

    def sub_value(self, a, b):
        log_mat("sub_value")
        if a.is_vector() and b.is_vector():
            return ValueVector(a.x - b.x, a.y - b.y, a.z - b.z, a.w - b.w)
        log_mat("sub_value : add arithmetic node...")
        node = ArithmeticNode(self, a, b, OperatorType.SUB)
        return ValueNode(node)

    def get_mapping(self, blender_node):
        if blender_node.mapping_in not in blender_node.inputs:
            return Value()
        socket = blender_node.inputs[blender_node.mapping_in]
        if socket.is_linked and len(socket.links) > 0:
            return self.get_value(blender_node, blender_node.mapping_in)
        return Value()
