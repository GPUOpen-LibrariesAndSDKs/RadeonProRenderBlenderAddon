import sys

import bpy

import pyrpr
import pyrprx
from rprblender.utils import key as object_key
from rprblender.utils import logging
from rprblender.utils import material as mat_utils
from . import RPR_Properties


log = logging.Log(tag='Material')


class RPR_MaterialParser(RPR_Properties):
    def sync(self, rpr_context) -> pyrprx.Material:
        mat = self.id_data
        log("Syncing material: %s" % mat.name)
        tree = getattr(mat, 'node_tree', None)

        if not tree:
            # "ERROR" shader
            return self.create_fake_material(rpr_context, (1.0, 0.0, 1.0, 1.0))

        # Look for output node
        node = mat_utils.find_rpr_output_node(tree)
        if not node:
            node = mat_utils.find_cycles_output_node(tree)
            if not node:
                log("No valid output node found!")
                return self.create_fake_material(rpr_context, (1.0, 0.0, 1.0, 1.0))
            else:
                log("Blender output node found: {}".format(node))
                try:
                    result = self.parse_cycles_output_node(rpr_context, node)
                except Exception as e:
                    tb = sys.exc_info()[2]
                    log("Cycles material parsing exception {}".format(e.with_traceback(tb)))
                    result = self.create_fake_material(rpr_context, (1.0, 0.0, 1.0, 1.0))
                return result
        if not hasattr(node, 'sync'):
            log("No valid output node found!")
            return self.create_fake_material(rpr_context, (1.0, 0.0, 1.0, 1.0))

        log("Output node {}".format(node))

        # Parse it
        material = node.sync(rpr_context)
        log("Material parsed as {}".format(material))

        # Fake material for tests
        if not material:
            color = (0.9, 0.4, 0.4, 1.0)
            material = self.create_fake_material(rpr_context, color)

        return material

    @staticmethod
    def get_socket(node, name=None, index=None):
        if name:
            try:
                socket = node.inputs[name]
            except KeyError:
                return None
        elif index:
            try:
                socket = node.inputs[index]
            except IndexError:
                return None
        else:
            return None

        log("get_socket({}, {}, {}): {}; linked {}; links number {}".format
            (node, name, index, socket, socket.is_linked, len(socket.links)))
        if socket.is_linked and len(socket.links) > 0:
            return socket.links[0].from_socket
        return None

    def create_fake_material(self, rpr_context, color: tuple) -> pyrprx.Material:
        null_vector = (0, 0, 0, 0)
        key = object_key(self.id_data)
        if not key:
            key = "Unnamed_{}".format(self)
        rpr_mat = rpr_context.create_material(key, pyrprx.MATERIAL_UBER)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_DIFFUSE_COLOR, color)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, (1.0, 1.0, 1.0, 1.0))
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS, (0.5, 0.5, 0.5, 0.5))
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_WEIGHT, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_EMISSION_WEIGHT, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SSS_WEIGHT, null_vector)
        return rpr_mat

    def parse_cycles_output_node(self, rpr_context, node):
        material = None
        input = self.get_socket(node, name='Surface')  # 'Surface'
        log("Material Output input['Surface'] linked to {}".format(input))
        input_node = input.node
        log("syncing {}".format(input_node))
        # TODO replace with conversion "Cycles -> RPR" table
        if input_node.bl_idname == 'ShaderNodeBsdfPrincipled':
            material = self.parse_cycles_principled(rpr_context, input_node)
        elif input_node.bl_idname == 'ShaderNodeBsdfPrincipled':
            material = input_node.sync(rpr_context)
        return material

    def parse_cycles_principled(self, rpr_context, node) -> pyrprx.Material:
        def get_value(name):
            socket = node.inputs[name]
            log("input {} value is {}".format(name, socket.default_value))
            if socket:
                val = socket.default_value
                if isinstance(val, float) or isinstance(val, int):
                    return (val, val, val, val)
                elif len(val) == 3:
                    return (val[0], val[1], val[2], 1.0)
                elif len(val) == 4:
                    return val[0:4]
                raise Exception("Unknown socket '{}' value type '{}'".format(socket, type(socket)))

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

        key = object_key(self.id_data)
        if not key:
            key = "Unnamed_{}".format(self)
        rpr_mat = rpr_context.create_material(key, pyrprx.MATERIAL_UBER)

        # Base color -> Diffuse (always on, except for glass)
        if is_not_glass:
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_DIFFUSE_COLOR, base_color)
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, one_vector)
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS, roughness)
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, null_vector)
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, null_vector)
        else:
            # TODO replace with mix of diffuse/refractive shaders with transmission as a mask/factor
            # TODO also adjust to core changes
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, null_vector)

        # Metallic -> Reflection (always on unless specular is set to non-physical 0.0)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT, specular)
        # mode 'metal' unless transmission is set and metallic is 0
        if is_not_glass:
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                                  pyrprx.UBER_MATERIAL_REFLECTION_MODE_METALNESS)
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_METALNESS, metalness)
        else:
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                                  pyrprx.UBER_MATERIAL_REFLECTION_MODE_PBR)
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_IOR, ior)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_COLOR, base_color)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_ROUGHNESS, roughness)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY, anisotropic)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY_ROTATION, anisotropic_rotation)

        # Clearcloat -> Coating
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_COLOR, one_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_WEIGHT, clearcoat)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_ROUGHNESS, clearcoat_roughness)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_THICKNESS, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_TRANSMISSION_COLOR, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_MODE,
                              pyrprx.UBER_MATERIAL_COATING_MODE_PBR)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_IOR, ior)

        # Sheen -> Sheen
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SHEEN_WEIGHT, sheen)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SHEEN, base_color)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SHEEN_TINT, sheen_tint)

        # No Emission for Cycles Principled BSDF
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_EMISSION_WEIGHT, null_vector)

        # Subsurface -> Subsurface
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SSS_WEIGHT, subsurface)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SSS_SCATTER_COLOR, subsurface_color)
        # these also need to be set for core SSS to work.
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, subsurface)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, one_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SSS_SCATTER_DISTANCE, subsurface_radius)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SSS_MULTISCATTER, pyrpr.FALSE)

        # Transmission -> Refraction
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT, transmission)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFRACTION_COLOR, base_color)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFRACTION_ROUGHNESS, transmission_roughness)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFRACTION_IOR, ior)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFRACTION_THIN_SURFACE, pyrpr.FALSE)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFRACTION_CAUSTICS, pyrpr.TRUE)

        return rpr_mat

    @classmethod
    def register(cls):
        log("Material: Register")
        bpy.types.Material.rpr = bpy.props.PointerProperty(
            name="RPR Material Settings",
            description="RPR material settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Material: Unregister")
        del bpy.types.Material.rpr

