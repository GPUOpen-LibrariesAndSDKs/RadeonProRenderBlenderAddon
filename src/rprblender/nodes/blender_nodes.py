"""
All parser classes should:
- override NodeParser with export() method
- override RuleNodeParser with class field: node
"""

import math
import numpy as np

from .node_parser import NodeParser, RuleNodeParser, MaterialError, get_node_parser_class
import pyrpr
import pyrprx

from rprblender.export import image
from rprblender.utils.conversion import convert_kelvins_to_rgb

from rprblender.utils import logging
log = logging.Log(tag='export.rpr_nodes')


''' TODO NODES:
    ShaderNodeUVMap
    ShaderNodeAttribute
    NodeGroups
    ShaderNodeHueSaturation
'''


ERROR_OUTPUT_COLOR = (1.0, 0.0, 1.0, 1.0)   # Corresponds Cycles error output color
ERROR_IMAGE_COLOR = (1.0, 0.0, 1.0, 1.0)    # Corresponds Cycles error image color
COLOR_GAMMA = 2.2
SSS_MIN_RADIUS = 0.0001

# RGB to BW conversion constants by R-G-B channels
RED_GRAYSCALE_COEF = 0.2126
GREEN_GRAYSCALE_COEF = 0.7152
BLUE_GRAYSCALE_COEF = 0.0722


class ShaderNodeOutputMaterial(NodeParser):
    # inputs: Surface, Volume, Displacement

    def export(self, input_socket_key='Surface'):

        rpr_node = self.get_input_link(input_socket_key)
        if input_socket_key == 'Surface':
            if isinstance(rpr_node, (pyrpr.MaterialNode, pyrprx.Material)):
                return rpr_node

            if not rpr_node:
                # checking if we have connected node to Volume socket
                volume_rpr_node = self.export('Volume')
                if volume_rpr_node :
                    rpr_node = self.rpr_context.create_material_node(
                        pyrpr.MATERIAL_NODE_TRANSPARENT)
                    rpr_node.set_input('color', (1.0, 1.0, 1.0))
                    return rpr_node

            raise MaterialError("Incorrect Surface input socket",
                                type(rpr_node), self.node, self.material)

        if input_socket_key == 'Volume':
            if isinstance(rpr_node, dict):
                return rpr_node

            raise MaterialError("Incorrect Volume input socket",
                                type(rpr_node), self.node, self.material)

        return None

    def final_export(self, input_socket_key='Surface'):
        try:
            return self.export(input_socket_key)

        except MaterialError as e:  # material nodes setup error, stop parsing and inform user
            log.error(e)

            if input_socket_key == 'Surface':
                # creating error shader
                rpr_node = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_PASSTHROUGH)
                rpr_node.set_input('color', ERROR_OUTPUT_COLOR)
                return rpr_node

            return None


class ShaderNodeAmbientOcclusion(NodeParser):
    # inputs: Color, Distance

    def export(self):
        radius = self.get_input_value('Distance')
        side = (-1.0, 0.0, 0.0, 0.0) if self.node.inside else (1.0, 0.0, 0.0, 0.0)

        ao_map = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_AO_MAP)
        ao_map.set_input('radius', radius)
        ao_map.set_input('side', side)

        # TODO: Properties samples, only_local, Normal input are not used yet

        if self.socket_out.name == 'AO':
            return ao_map

        color = self.get_input_value('Color')
        rpr_node = self.mul_node_value(color, ao_map)
        return rpr_node


class NodeReroute(NodeParser):
    # Just pass through the input

    def export(self):
        return self.get_input_link(0)


class ShaderNodeBrightContrast(RuleNodeParser):
    # inputs: Bright, Contrast, Color

    # Following formula should be used:
    #   color_out = max(Bright + (Color - 0.5) * (Contrast + 1) + 0.5, 0.0)
    # This formula was given from OSL shader code in cycles and modified to correspond to how it works in cycles
    # In simple operations it could be splitted into:
    #   a = Color - 0.5
    #   b = Contrast + 1.0
    #   c = a * b
    #   d = c + 0.5
    #   e = Bright + d
    #   color_out = max(e, 0.0)

    nodes = {
        "a": {
            "type": "-",
            "params": {
                "color0": "inputs.Color",
                "color1": 0.5,
            }
        },
        "b": {
            "type": "+",
            "params": {
                "color0": "inputs.Contrast",
                "color1": 1.0,
            }
        },
        "c": {
            "type": "*",
            "params": {
                "color0": "nodes.a",
                "color1": "nodes.b",
            }
        },
        "d": {
            "type": "+",
            "params": {
                "color0": "nodes.c",
                "color1": 0.5,
            }
        },
        "e": {
            "type": "+",
            "params": {
                "color0": "inputs.Bright",
                "color1": "nodes.d",
            }
        },
        "Color": { # output
            "type": "max",
            "params": {
                "color0": "nodes.e",
                "color1": 0.0,
            }
        }
    }


class ShaderNodeBsdfAnisotropic(RuleNodeParser):
    # inputs: Color, Roughness, Anisotropy, Rotation, Normal

    nodes = {
        "BSDF": {
            "type": pyrpr.MATERIAL_NODE_MICROFACET_ANISOTROPIC_REFLECTION,
            "params": {
                "color": "inputs.Color",
                "roughness": "inputs.Roughness",
                "anisotropic": "inputs.Anisotropy",
                "rotation": "inputs.Rotation",
                "normal": "normal:inputs.Normal"
            }
        }
    }
    # TODO: Use Tangent input and distribution property


class ShaderNodeBsdfDiffuse(RuleNodeParser):
    # inputs: Color, Roughness, Normal

    nodes = {
        "BSDF": {
            "type": pyrpr.MATERIAL_NODE_DIFFUSE,
            "params": {
                "color": "inputs.Color",
                "roughness": "inputs.Roughness",
                "normal": "normal:inputs.Normal"
            }
        }
    }


class ShaderNodeBsdfGlass(RuleNodeParser):
    # inputs: Color, Roughness, Normal, IOR

    nodes = {
        "BSDF": {
            "type": pyrpr.MATERIAL_NODE_MICROFACET_REFRACTION,
            "params": {
                "color": "inputs.Color",
                "roughness": "inputs.Roughness",
                "normal": "normal:inputs.Normal",
                "ior": "inputs.IOR"
            }
        }
    }
    # TODO: Has to be fixed, it is working like ShaderNodeBsdfRefraction


class ShaderNodeBsdfGlossy(RuleNodeParser):
    # inputs: Color, Roughness, Normal

    nodes = {
        "BSDF": {
            "type": pyrpr.MATERIAL_NODE_MICROFACET,
            "params": {
                "color": "inputs.Color",
                "roughness": "inputs.Roughness",
                "normal": "normal:inputs.Normal"
            }
        }
    }
    # TODO: Use distribution property


class ShaderNodeBsdfRefraction(RuleNodeParser):
    # inputs: Color, Roughness, Normal, IOR

    nodes = {
        "BSDF": {
            "type": pyrpr.MATERIAL_NODE_MICROFACET_REFRACTION,
            "params": {
                "color": "inputs.Color",
                "roughness": "inputs.Roughness",
                "normal": "normal:inputs.Normal",
                "ior": "inputs.IOR"
            }
        }
    }
    # TODO: Use distribution property


class ShaderNodeBsdfTranslucent(RuleNodeParser):
    # inputs: Color, Normal

    nodes = {
        "BSDF": {
            "type": pyrpr.MATERIAL_NODE_DIFFUSE_REFRACTION,
            "params": {
                "color": "inputs.Color",
                "normal": "normal:inputs.Normal"
            }
        }
    }


class ShaderNodeBsdfTransparent(RuleNodeParser):
    # inputs: Color

    nodes = {
        "BSDF": {
            "type": pyrpr.MATERIAL_NODE_TRANSPARENT,
            "params": {
                "color": "inputs.Color",
            }
        }
    }


class ShaderNodeBsdfVelvet(RuleNodeParser):
    # inputs: Color, Sigma

    nodes = {
        "BSDF": {
            "type": pyrprx.MATERIAL_UBER,
            "is_rprx": True,
            "params": {
                pyrprx.UBER_MATERIAL_DIFFUSE_COLOR: "inputs.Color",
                pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT: "inputs.Sigma",
                pyrprx.UBER_MATERIAL_DIFFUSE_NORMAL: "normal:inputs.Normal",
                pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT: 0.0,
                pyrprx.UBER_MATERIAL_SHEEN_WEIGHT: 1.0,
                pyrprx.UBER_MATERIAL_SHEEN_TINT: "inputs.Sigma",
                pyrprx.UBER_MATERIAL_SHEEN: "inputs.Color"
            }
        }
    }
    # TODO: Has to be fixed, probably diffuse is not needed here


class ShaderNodeEmission(RuleNodeParser):
    # inputs: Color, Strength

    nodes =  {
        # emission_color = Color * Strength
        "emission_color": {
            "type": "*",
            "params": {
                "color0": "inputs.Color",
                "color1": "inputs.Strength",
            }
        },
        "emission_node": {
            "type": pyrpr.MATERIAL_NODE_EMISSIVE,
            "params": {
                "color": "nodes.emission_color"
            }
        },
        "Emission": {
            "type": pyrpr.MATERIAL_NODE_TWOSIDED,
            "params": {
                "frontface": "nodes.emission_node",
                "backface": "nodes.emission_node"
            }
        }
    }


class ShaderNodeFresnel(RuleNodeParser):
    # inputs: IOR, Normal

    nodes = {
        "Fac": {
            "type": pyrpr.MATERIAL_NODE_FRESNEL,
            "params": {
                "ior": "inputs.IOR",
                "normal": "normal:inputs.Normal"
            }
        }
    }

class ShaderNodeLayerWeight(NodeParser):
    # inputs: Blend, Normal
    ''' This should do a fresnel and blend based on that.  Use Blend for ior 
        Thif follows the cycles OSL code '''

    def export(self):
        blend = self.get_input_value('Blend')
        normal = self.get_input_normal('Normal')
        if not normal:
            normal = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP)
            normal.set_input('value', pyrpr.MATERIAL_NODE_LOOKUP_N)
        I = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP)
        I.set_input('value', pyrpr.MATERIAL_NODE_LOOKUP_INVEC)
        IdotN = self.dot3_node_value(I, normal)
        
        if self.socket_out.name == 'Fresnel':
            # backfacing if I.N < 0
            backfacing = self.arithmetic_node_value(IdotN, 0.0, pyrpr.MATERIAL_NODE_OP_GREATER)

            eta = self.max_node_value(self.sub_node_value(1.0, blend), 0.00001)
            # if not backfacing eta = 1/eta
            eta2 = self.arithmetic_node_value(backfacing, eta, pyrpr.MATERIAL_NODE_OP_TERNARY)
            eta2.set_input('color2', self.div_node_value(1.0, eta))
            

            fresnel = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_FRESNEL)
            fresnel.set_input('normal', normal)
            fresnel.set_input('ior', eta2)

            return fresnel

        else:
            # Facing input
            blend2 = self.min_node_value(self.max_node_value(blend, 0.0), .99999)
            blend_less_than_half = self.arithmetic_node_value(blend2, 0.5, pyrpr.MATERIAL_NODE_OP_LOWER)
            blend3 = self.arithmetic_node_value(blend_less_than_half, self.mul_node_value(blend2, 2.0), pyrpr.MATERIAL_NODE_OP_TERNARY)
            blend3.set_input('color2', self.div_node_value(0.5, self.sub_node_value(1.0, blend2)))

            abs_IdotN = self.arithmetic_node_value(IdotN, None, pyrpr.MATERIAL_NODE_OP_ABS)
            facing = self.arithmetic_node_value(abs_IdotN, blend3, pyrpr.MATERIAL_NODE_OP_POW)
            return self.sub_node_value(1.0, facing)

        

class ShaderNodeGamma(RuleNodeParser):
    # inputs: Color, Gamma

    nodes = {
        "Color": {
            "type": pyrpr.MATERIAL_NODE_ARITHMETIC,
            "params": {
                "color0": "inputs.Color",
                "color1": "inputs.Gamma",
                "op": pyrpr.MATERIAL_NODE_OP_POW
            }
        }
    }


class ShaderNodeInvert(RuleNodeParser):
    # inputs: Fac, Color

    nodes = {
        "invert": {
            "type": "-",
            "params": {
                "color0": 1.0,
                "color1": "inputs.Color",
            }
        },
        "Color": {
            "type": "blend",
            "params": {
                "color0": "inputs.Color",
                "color1": "nodes.invert",
                "weight": "inputs.Fac"
            }
        }
    }


class ShaderNodeSubsurfaceScattering(RuleNodeParser):
    # inputs: Color, Scale, Radius, Texture Blur, Normal

    nodes = {
        "radius_scale": {
            "type": "*",
            "params": {
                "color0": "inputs.Scale",
                "color1": "inputs.Radius",
            }
        },
        "radius": {
            "type": "max",
            "params": {
                "color0": "nodes.radius_scale",
                "color1": SSS_MIN_RADIUS
            }
        },
        "BSSRDF": {
            "type": pyrprx.MATERIAL_UBER,
            "is_rprx": True,
            "params": {
                pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT: 1.0,
                pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT: 0.0,
                pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT: 1.0,
                pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR: (1.0, 1.0, 1.0, 1.0),
                pyrprx.UBER_MATERIAL_SSS_WEIGHT: 1.0,
                pyrprx.UBER_MATERIAL_SSS_SCATTER_COLOR: "inputs.Color",
                pyrprx.UBER_MATERIAL_SSS_SCATTER_DISTANCE: "nodes.radius",
                pyrprx.UBER_MATERIAL_DIFFUSE_NORMAL: "normal:inputs.Normal"
            }
        }
    }
    # TODO: Use Texture Blur input and falloff property. Check normal


class ShaderNodeTexChecker(NodeParser):
    # inputs: Vector, Color1, Color2, Scale

    def export(self):
        # TODO: TexChecker export has to be fixed because cycles provides some different results.
        #  input.Vector is not applied yet

        scale = self.get_input_value('Scale')
        scale_rpr = self.mul_node_value(scale, 0.125)  # in RPR it is divided by 8 (or multiplied by 0.125)

        vector = self.get_input_link('Vector')
        if vector is None:
            vector = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP)
            vector.set_input('value', pyrpr.MATERIAL_NODE_LOOKUP_UV)

        uv = self.mul_node_value(scale_rpr, vector)

        checker = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_CHECKER_TEXTURE)
        checker.set_input('uv', uv)

        if self.socket_out.name == 'Fac':
            return checker

        color1 = self.get_input_value('Color1')
        color2 = self.get_input_value('Color2')
        blend = self.blend_node_value(color1, color2, checker)
        return blend


class ShaderNodeTexImage(NodeParser):
    def export(self):
        if not self.node.image:
            return ERROR_IMAGE_COLOR if self.socket_out.name == 'Color' else ERROR_IMAGE_COLOR[3]

        try:
            rpr_image = image.sync(self.rpr_context, self.node.image)
        except ValueError as e:
            raise MaterialError(e, self.node, self.material)

        wrap_mapping = {
            'REPEAT': pyrpr.IMAGE_WRAP_TYPE_REPEAT,
            'EXTEND': pyrpr.IMAGE_WRAP_TYPE_CLAMP_TO_EDGE,
            'CLIP': pyrpr.IMAGE_WRAP_TYPE_CLAMP_ZERO
        }
        rpr_image.set_wrap(wrap_mapping[self.node.extension])

        # TODO: Implement using node properties: interpolation, projection
        if self.node.interpolation != 'Linear':
            log.warn("Ignoring unsupported texture interpolation", self.node.interpolation, self.node, self.material)
        if self.node.projection != 'FLAT':
            log.warn("Ignoring unsupported texture projection", self.node.projection, self.node, self.material)

        rpr_node = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_IMAGE_TEXTURE)
        rpr_node.set_input('data', rpr_image)

        vector = self.get_input_link('Vector')
        if vector is not None:
            rpr_node.set_input('uv', vector)

        if self.socket_out.name == 'Alpha':
            rpr_node = self.get_w_node_value(rpr_node)

        return rpr_node


class ShaderNodeBsdfPrincipled(NodeParser):
    # inputs: Base Color, Roughness,
    #    Subsurface, Subsurface Radius, Subsurface Color,
    #    Metallic, Specular, Specular Tint,
    #    Anisotropic, Anisotropic Rotation,
    #    Clearcoat, Clearcoat Roughness, Clearcoat Normal,
    #    Sheen, Sheen Tint,
    #    IOR, Transmission, Transmission Roughness,
    #    Normal, Tangent

    def export(self):
        def enabled(val):
            if val is None:
                return False

            if isinstance(val, float) and math.isclose(val, 0.0):
                return False

            return True

        # Getting require inputs. Note: if some inputs are not needed they won't be taken
        base_color = self.get_input_value('Base Color')

        subsurface = self.get_input_value('Subsurface')
        subsurface_radius = None
        subsurface_color = None
        if enabled(subsurface):
            subsurface_radius = self.get_input_value('Subsurface Radius')
            subsurface_color = self.get_input_value('Subsurface Color')

        metallic = self.get_input_value('Metallic')
        roughness = self.get_input_value('Roughness')

        specular = self.get_input_value('Specular')
        anisotropic = None
        anisotropic_rotation = None
        if enabled(specular):
            # TODO: use Specular Tint input
            anisotropic = self.get_input_value('Anisotropic')
            if enabled(anisotropic):
                anisotropic_rotation = self.get_input_value('Anisotropic Rotation')

        sheen = self.get_input_value('Sheen')
        sheen_tint = None
        if enabled(sheen):
            sheen_tint = self.get_input_value('Sheen Tint')

        clearcoat = self.get_input_value('Clearcoat')
        clearcoat_roughness = None
        clearcoat_normal = None
        if enabled(clearcoat):
            clearcoat_roughness = self.get_input_value('Clearcoat Roughness')
            clearcoat_normal = self.get_input_normal('Clearcoat Normal')

        ior = self.get_input_value('IOR')

        transmission = self.get_input_value('Transmission')
        transmission_roughness = None
        if enabled(transmission):
            transmission_roughness = self.get_input_value('Transmission Roughness')

        normal = self.get_input_normal('Normal')

        # TODO: use Tangent input

        # Creating uber material and set inputs to it
        rpr_node = self.rpr_context.create_x_material_node(pyrprx.MATERIAL_UBER)

        diffuse = self.sub_node_value(1.0, transmission) # TODO: this has to be checked

        if enabled(diffuse):
            rpr_node.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_COLOR, base_color)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, 1.0)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS, roughness)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, 0.0)

            if enabled(normal):
                rpr_node.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_NORMAL, normal)
        else:
            rpr_node.set_input(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, 0.0)

        # Metallic -> Reflection (always on unless specular is set to non-physical 0.0)
        if enabled(specular):
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT, specular)
            # TODO: check, probably need to multiply specular by 2

            # mode 'metal' unless transmission is set and metallic is 0
            if enabled(transmission) and not enabled(metallic):
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_MODE, pyrprx.UBER_MATERIAL_REFLECTION_MODE_PBR)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_IOR, ior)
            else:
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_MODE, pyrprx.UBER_MATERIAL_REFLECTION_MODE_METALNESS)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_METALNESS, metallic)

            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_COLOR, base_color)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ROUGHNESS, roughness)

            if enabled(normal):
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_NORMAL, normal)

            if enabled(anisotropic):
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY, anisotropic)
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY_ROTATION, anisotropic_rotation)

        # Clearcloat
        if enabled(clearcoat):
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_COLOR, (1.0, 1.0, 1.0, 1.0))
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_WEIGHT, clearcoat)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_ROUGHNESS, clearcoat_roughness)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_THICKNESS, 0.0)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_TRANSMISSION_COLOR, (0.0, 0.0, 0.0, 0.0))
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_MODE, pyrprx.UBER_MATERIAL_COATING_MODE_PBR)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_IOR, ior)

            if enabled(clearcoat_normal):
                rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_NORMAL, clearcoat_normal)
            elif enabled(normal):
                rpr_node.set_input(pyrprx.UBER_MATERIAL_COATING_NORMAL, normal)

        # Sheen
        if enabled(sheen):
            rpr_node.set_input(pyrprx.UBER_MATERIAL_SHEEN_WEIGHT, sheen)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_SHEEN, base_color)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_SHEEN_TINT, sheen_tint)

        # Subsurface
        if enabled(subsurface):
            rpr_node.set_input(pyrprx.UBER_MATERIAL_SSS_WEIGHT, subsurface)
            rpr_node.set_input(pyrprx.UBER_MATERIAL_SSS_SCATTER_COLOR, subsurface_color)

            # check for 0 channel value(for Cycles it means "light shall not pass" unlike "pass it all" of RPR)
            # that's why we check it with small value like 0.0001
            subsurface_radius = self.max_node_value(subsurface_radius, SSS_MIN_RADIUS)
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

            if enabled(normal):
                rpr_node.set_input(pyrprx.UBER_MATERIAL_REFRACTION_NORMAL, normal)

        return rpr_node


class ShaderNodeNewGeometry(RuleNodeParser):
    # outputs: Position, Normal, Tangent, True Normal, Incoming, Parametric, Backfacing, Pointiness
    # Supported outputs by RPR: Position, Normal, Incoming

    nodes = {
        "Position": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                "value": pyrpr.MATERIAL_NODE_LOOKUP_P,
            }
        },
        "Normal": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                "value": pyrpr.MATERIAL_NODE_LOOKUP_N,
            }
        },
        # TODO: Implement support of True Normal

        "invec": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                "value": pyrpr.MATERIAL_NODE_LOOKUP_INVEC,
            }
        },
        "Incoming": {
            "type": "*",
            "params": {
                "color0": -1.0,
                "color1": "nodes.invec"
            }
        },
    }


class ShaderNodeAddShader(NodeParser):
    # inputs: 0, 1 - blender confusingly has inputs with the same name.
    def export(self):
        shader1 = self.get_input_link(0)
        shader2 = self.get_input_link(1)

        if shader1 is None and shader2 is None:
            return None

        if shader1 is None:
            return shader2

        if shader2 is None:
            return shader1

        rpr_node = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_ADD)
        rpr_node.set_input('color0', shader1)
        rpr_node.set_input('color1', shader2)
        return rpr_node


class ShaderNodeTexCoord(RuleNodeParser):
    # outputs: Generated, Normal, UV, Object, Camera, Window, Reflection
    # Supported outputs by RPR: Normal, UV

    nodes = {
        "Generated": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                "value": pyrpr.MATERIAL_NODE_LOOKUP_UV,
            },
            "warn": "TexCoord Generated output is not supported, UV will be used"
        },
        "Normal": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                "value": pyrpr.MATERIAL_NODE_LOOKUP_N,
            }
        },
        "UV": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                "value": pyrpr.MATERIAL_NODE_LOOKUP_UV,
            }
        },
        "Object": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                "value": pyrpr.MATERIAL_NODE_LOOKUP_P,
            },
            "warn": "TexCoord Object output is not supported, world coordinate will be used"
        }

    }


class ShaderNodeLightFalloff(NodeParser):
    ''' we don't actually do light falloff in RPR.  
        So we're mainly going to pass through "strength" '''
    def export(self):
        # This shader is used in materials preview, no need to spam log.warn() here. Changing to log.debug()
        log.debug("Light Falloff node is not supported, only strength will be taken", self.node, self.material)

        return self.get_input_default('Strength')


class ShaderNodeMixRGB(NodeParser):

    def export(self):
        fac = self.get_input_value('Fac')
        color1 = self.get_input_value('Color1')
        color2 = self.get_input_value('Color2')

        # these mix types are copied from cycles OSL
        blend_type = self.node.blend_type
        if blend_type in ('MIX', 'COLOR'):
            rpr_node = self.blend_node_value(color1, color2, fac)

        elif blend_type == 'ADD':
            add = self.add_node_value(color1, color2)
            rpr_node = self.blend_node_value(color1, add, fac)

        elif blend_type == 'MULTIPLY':
            mul = self.mul_node_value(color1, color2)
            rpr_node = self.blend_node_value(color1, mul, fac)

        elif blend_type == 'SUBTRACT':
            sub = self.sub_node_value(color1, color2)
            rpr_node = self.blend_node_value(color1, sub, fac)

        elif blend_type == 'DIVIDE':
            div = self.arithmetic_node_value(color1, color2, pyrpr.MATERIAL_NODE_OP_DIV)
            rpr_node = self.blend_node_value(color1, div, fac)

        elif blend_type == 'DIFFERENCE':
            sub = self.sub_node_value(color1, color2)
            abs = self.arithmetic_node_value(sub, None, pyrpr.MATERIAL_NODE_OP_ABS)
            rpr_node = self.blend_node_value(color1, abs, fac)

        elif blend_type == 'DARKEN':
            min_val = self.min_node_value(color1, color2)
            rpr_node = self.blend_node_value(color1, min_val, fac)

        elif blend_type == 'VALUE':
            rpr_node = color1

        else:
            # TODO: finish other mix types: SATURATION, HUE, LINEAR_LIGHT, SOFT_LIGHT, OVERLAY, DODGE, SCREEN, LIGHTEN, BURN
            log.warn("Ignoring unsupported Blend Type", blend_type, self.node, self.material)
            return None

        if self.node.use_clamp:
            rpr_node = self.max_node_value(self.min_node_value(rpr_node, 1.0), 0.0)

        return rpr_node


class ShaderNodeMath(NodeParser):
    ''' simply map the blender op types to rpr op types with included map.
        We could be more correct with "round" but I've never seen this used. '''
    # map blender node op to rpr math op and number of inputs
    math_map = {
        'ADD': (pyrpr.MATERIAL_NODE_OP_ADD, 2),
        'SUBTRACT': (pyrpr.MATERIAL_NODE_OP_SUB, 2),
        'MULTIPLY': (pyrpr.MATERIAL_NODE_OP_MUL, 2),
        'DIVIDE': (pyrpr.MATERIAL_NODE_OP_DIV, 2),
        'SINE': (pyrpr.MATERIAL_NODE_OP_SIN, 1),
        'COSINE': (pyrpr.MATERIAL_NODE_OP_COS, 1),
        'TANGENT': (pyrpr.MATERIAL_NODE_OP_TAN, 1),
        'ARCSINE': (pyrpr.MATERIAL_NODE_OP_ASIN, 1),
        'ARCCOSINE': (pyrpr.MATERIAL_NODE_OP_ACOS, 1),
        'ARCTANGENT': (pyrpr.MATERIAL_NODE_OP_ATAN, 1),
        'POWER': (pyrpr.MATERIAL_NODE_OP_POW, 2),
        'LOGARITHM': (pyrpr.MATERIAL_NODE_OP_LOG, 1),
        'MINIMUM': (pyrpr.MATERIAL_NODE_OP_MIN, 2),
        'MAXIMUM': (pyrpr.MATERIAL_NODE_OP_MAX, 2),
        'LESS_THAN': (pyrpr.MATERIAL_NODE_OP_LOWER, 2),
        'GREATER_THAN': (pyrpr.MATERIAL_NODE_OP_GREATER, 2),
        'MODULO': (pyrpr.MATERIAL_NODE_OP_MOD, 2),
        'ABSOLUTE': (pyrpr.MATERIAL_NODE_OP_ABS, 1),
        'FLOOR': (pyrpr.MATERIAL_NODE_OP_FLOOR, 1),
    }

    def export(self):
        ''' special cases 
            'SQRT': 
            'ARCTAN2':
            'FRACT': 
            'CEIL': 
            'ROUND':
        '''

        blender_op = self.node.operation
        if blender_op in self.math_map:
            # this is the simple case we can handle automatically
            in1 = self.get_input_value(0)
            rpr_op, num_inputs = self.math_map[blender_op]
            in2 = self.get_input_value(1) if num_inputs == 2 else None

            # if use clamp is set we don't want this to be the out node so don't use_key
            math_node = self.arithmetic_node_value(in1, in2, rpr_op)

        # special cases
        elif blender_op == 'SQRT':
            # use pow with 1/power
            in1 = self.get_input_value(0)
            in2 = self.get_input_value(1)

            pow_inv = self.div_node_value(1.0, in2)
            math_node = self.arithmetic_node_value(in1, pow_inv, pyrpr.MATERIAL_NODE_OP_POW)

        elif blender_op == 'ARCTAN2':
            # arctan in1/in2
            in1 = self.get_input_value(0)
            in2 = self.get_input_value(1)

            div = self.div_node_value(in1, in2)
            math_node = self.arithmetic_node_value(div, None, pyrpr.MATERIAL_NODE_OP_ATAN)

        elif blender_op == 'FRACT':
            # v1 % 1.0
            in1 = self.get_input_value(0)
            math_node = self.arithmetic_node_value(in1, 1.0, pyrpr.MATERIAL_NODE_OP_MOD)
       
        elif blender_op == 'CEIL':
            # v1 + (1 - mod(v1, 1.0))
            in1 = self.get_input_value(0)
            
            mod = self.arithmetic_node_value(in1, 1.0, pyrpr.MATERIAL_NODE_OP_MOD)
            one_minus = self.sub_node_value(1.0, mod)
            math_node = self.add_node_value(in1, one_minus)

        elif blender_op == 'ROUND':
            # ceil if (v1 % 1.0 ) > .5 else floor
            in1 = self.get_input_value(0)
            
            mod = self.arithmetic_node_value(in1, 1.0, pyrpr.MATERIAL_NODE_OP_MOD)
            one_minus = self.sub_node_value(1.0, mod)
            ceil = self.add_node_value(in1, one_minus)
            floor = self.arithmetic_node_value(in1, None, pyrpr.MATERIAL_NODE_OP_FLOOR)
            greater = self.arithmetic_node_value(mod, 0.5, pyrpr.MATERIAL_NODE_OP_GREATER)
            # we need to use a ternery op here for if, so set color2 after
            math_node = self.arithmetic_node_value(greater, ceil, pyrpr.MATERIAL_NODE_OP_TERNARY)
            math_node.set_input('color2', floor)

        if self.node.use_clamp:
            min_node = self.min_node_value(1.0, math_node)
            return self.max_node_value(0.0, min_node)
        else:
            return math_node


class ShaderNodeVectorMath(NodeParser):
    """ Apply vector math operations assuming Blender node was designed to work with 3-axis vectors """
    # map blender vector math node operations to rpr math operations and number of inputs
    vector_math_map = {
        'ADD': (pyrpr.MATERIAL_NODE_OP_ADD, 2),
        'SUBTRACT': (pyrpr.MATERIAL_NODE_OP_SUB, 2),
        'AVERAGE': (pyrpr.MATERIAL_NODE_OP_AVERAGE_XYZ, 2),
        'DOT_PRODUCT': (pyrpr.MATERIAL_NODE_OP_DOT3, 2),
        'CROSS_PRODUCT': (pyrpr.MATERIAL_NODE_OP_CROSS3, 2),
        'NORMALIZE': (pyrpr.MATERIAL_NODE_OP_NORMALIZE3, 1),
    }

    def export(self):
        blender_op = self.node.operation

        in1 = self.get_input_value(0)
        rpr_op, num_inputs = self.vector_math_map[blender_op]
        in2 = self.get_input_value(1) if num_inputs == 2 else None

        math_node = self.arithmetic_node_value(in1, in2, rpr_op)

        # Apply RGB to BW conversion for "Value" output
        if self.socket_out.name == 'Value':
            red_val = self.mul_node_value(self.get_x_node_value(math_node),
                                          (RED_GRAYSCALE_COEF, RED_GRAYSCALE_COEF, RED_GRAYSCALE_COEF, 0.0))
            green_val = self.mul_node_value(self.get_y_node_value(math_node),
                                            (GREEN_GRAYSCALE_COEF, GREEN_GRAYSCALE_COEF, GREEN_GRAYSCALE_COEF, 0.0))
            blue_val = self.mul_node_value(self.get_z_node_value(math_node),
                                           (BLUE_GRAYSCALE_COEF, BLUE_GRAYSCALE_COEF, BLUE_GRAYSCALE_COEF, 0.0))
            alpha_val = self.mul_node_value(self.get_w_node_value(math_node), (0.0, 0.0, 0.0, 1.0))
            res = self.add_node_value(red_val, green_val)
            res = self.add_node_value(res, blue_val)
            res = self.add_node_value(res, alpha_val)
            return res

        return math_node


class ShaderNodeMixShader(NodeParser):
    # inputs = ['Fac', 1, 2]

    def export(self):
        factor = self.get_input_value('Fac')

        if isinstance(factor, float):
            socket_key = 1 if math.isclose(factor, 0.0) else \
                         2 if math.isclose(factor, 1.0) else \
                         None
            if socket_key:
                shader = self.get_input_link(socket_key)
                if shader:
                    return shader
                return self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_DIFFUSE)

        shader1 = self.get_input_link(1)
        shader2 = self.get_input_link(2)

        rpr_node = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_BLEND)
        rpr_node.set_input('weight', factor)
        if shader1:
            rpr_node.set_input('color0', shader1)
        if shader2:
            rpr_node.set_input('color1', shader2)

        return rpr_node


class ShaderNodeNormalMap(NodeParser):
    """ blends between input vec and N based on strength """
    # inputs: Strength, Color

    def export(self):
        color = self.get_input_value('Color')
        strength = self.get_input_value('Strength')

        rpr_node = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_NORMAL_MAP)
        rpr_node.set_input('color', color)
        rpr_node.set_input('bumpscale', strength)

        if self.node.space != 'TANGENT':
            log.warn("Ignoring unsupported normal map space", self.node.space, self.node, self.material)

        if self.node.uv_map:
            log.warn("Ignoring unsupported normal map uv_map", self.node.uv_map, self.node, self.material)

        return rpr_node


class ShaderNodeNormal(NodeParser):
    """ Has two ouputs "normal" which is just to use the normal output, and dot 
        which dot products normal output and input """
    
    def export(self):
        normalized_n = self.arithmetic_node_value(self.get_output_default(), None, pyrpr.MATERIAL_NODE_OP_NORMALIZE3)
        if self.socket_out.name == 'Normal':
            return normalized_n
        else:
            normalized_in = self.arithmetic_node_value(self.get_input_value('Normal'), None, pyrpr.MATERIAL_NODE_OP_NORMALIZE3)
            return self.dot3_node_value(normalized_n, normalized_in)


class ShaderNodeBump(NodeParser):
    def export(self):
        strength = self.get_input_value('Strength')
        distance = self.get_input_value('Distance')
        height = self.get_input_link('Height')

        color = distance
        if height is not None:
            color = self.mul_node_value(height, distance)

        if self.node.invert:
            color = self.mul_node_value(-1.0, color)

        rpr_node = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_BUMP_MAP)
        rpr_node.set_input('color', color)
        rpr_node.set_input('bumpscale', strength)

        # TODO: Use Normal input

        return rpr_node


class ShaderNodeValue(NodeParser):
    """ simply return val """

    def export(self):
        return self.get_output_default()


class ShaderNodeRGB(NodeParser):
    """ simply return val """
    
    def export(self):
        return self.get_output_default()


class ShaderNodeBlackbody(NodeParser):
    """Return RGB color by blackbody temperature
        1.  Create a pre-computed buffer 1000-40000 by 100's
        2.  Set that to rpr_buffer
        3.  Read buffer node material
    """

    def export(self):
        link = self.get_input_link('Temperature')
        if link:
            temp_buffer = []
            for t in range(1000, 40000, 100):
                r,g,b = convert_kelvins_to_rgb(t)
                temp_buffer.append([r,g,b,1.0])
            arr = np.array(temp_buffer, dtype=np.float32)
            # create the temperature buffer
            rpr_buffer = self.rpr_context.create_buffer(arr, pyrpr.BUFFER_ELEMENT_TYPE_FLOAT32)

            # convert input temperature to value to lookup in buffer - 
            # uv lookup 1000 - 40000 by 100
            math1 = self.sub_node_value(link, 1000)
            math2 = self.div_node_value(math1, 100)

            temperature = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER)
            temperature.set_input('data', rpr_buffer)
            temperature.set_input('uv', math2)
            return temperature
        else:
            return convert_kelvins_to_rgb(self.get_input_default('Temperature'))


class ShaderNodeValToRGB(NodeParser):
    """ Creates an RPR_Buffer from ramp, and samples that in node.
    """
    def export(self):
        ''' create a buffer from ramp data and sample that in nodes if connected '''
        buffer_size = 256 # hard code, this is what cycles does 

        link = self.get_input_link('Fac')
        if link:
            buff = []
            for i in range(buffer_size):
                buff.append(self.node.color_ramp.evaluate(float(i/(buffer_size - 1))))
            
            arr = np.array(buff, dtype=np.float32)
            # export the temperature buffer once to conserve memory
            rpr_buffer = self.rpr_context.create_buffer(arr, pyrpr.BUFFER_ELEMENT_TYPE_FLOAT32)

            uv = self.mul_node_value(link, float(buffer_size))
            read = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER)
            read.set_input('data', rpr_buffer)
            read.set_input('uv', uv)
            if self.socket_out.name == 'Alpha':
                return self.get_w_node_value(read)
            else:
                return read
        else:
            # just eval value
            val = self.node.color_ramp.evaluate(self.get_input_default('Fac'))
            if self.socket_out.name == 'Alpha':
                return val[3]
            else:
                return val


class ShaderNodeTexGradient(NodeParser):
    """ Makes a gradiant on vector input or P
    """
    def export(self):
        ''' create a buffer from ramp data and sample that in nodes if connected '''
        vec = self.get_input_link('Vector')
        if vec is None:
            vec = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP)
            vec.set_input('value', pyrpr.MATERIAL_NODE_LOOKUP_P)
        
        gradiant_type = self.node.gradient_type
        x = self.get_x_node_value(vec)
        if gradiant_type == 'LINEAR':
            val = x
        elif gradiant_type == 'QUADRATIC':
            r = self.max_node_value(x, 0.0)
            val = self.mul_node_value(r, r)
        elif gradiant_type == 'EASING':
            r = self.min_node_value(self.max_node_value(x, 0.0), 1.0)
            t = self.mul_node_value(r, r)
            # 3.0 * t - 2.0 * t * r
            val = self.sub_node_value(self.mul_node_value(t, 3.0),
                                    self.mul_node_value(2.0, self.mul_node_value(t, r)))
        elif gradiant_type == 'DIAGONAL':
            y = self.get_y_node_value(vec)
            val = self.mul_node_value(self.add_node_value(x, y), 0.5)
        elif gradiant_type == 'RADIAL':
            y = self.get_y_node_value(vec)
            atan2 = self.arithmetic_node_value(y, x, pyrpr.MATERIAL_NODE_OP_ATAN)
            val = self.add_node_value(self.div_node_value(atan2, 2.0 * math.pi), 0.5)
        else:
            # r = max(1.0 - length, 0.0);
            length = self.arithmetic_node_value(vec, None, pyrpr.MATERIAL_NODE_OP_LENGTH3)
            r = self.max_node_value(self.sub_node_value(1.0, length), 0.0)
            if gradiant_type  == 'QUADRATIC_SPHERE':
                val = self.mul_node_value(r, r)
            else: # 'SPHERICAL'
                val = r

        return val



class ShaderNodeRGBCurve(NodeParser):
    """ Similar to color ramp, except read each channel and apply mapping
        There are two inputs here, color and Fac.  What cycles does is remap color with the mapping
        and mix between in color and remapped one with fac.
    """
    def export(self):
        ''' create a buffer from ramp data and sample that in nodes if connected '''
        buffer_size = 256 # hard code, this is what cycles does 

        in_col = self.get_input_link('Color')
        fac = self.get_input_value('Fac')

        # these need to be initialized for some reason
        self.node.mapping.initialize()

        if in_col:
            buff = []
            for i in range(buffer_size):
                buff.append([self.node.mapping.curves[n].evaluate(float(i/(buffer_size - 1))) for n in range(4)])
            
            arr = np.array(buff, dtype=np.float32)
            # export the temperature buffer once to conserve memory
            rpr_buffer = self.rpr_context.create_buffer(arr, pyrpr.BUFFER_ELEMENT_TYPE_FLOAT32)

            # apply mapping to each channel
            select_r = self.get_x_node_value(in_col)
            mul_r = self.mul_node_value(select_r, float(buffer_size))
            map_r = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER)
            map_r.set_input('data', rpr_buffer)
            map_r.set_input('uv', mul_r)

            select_g = self.get_y_node_value(in_col)
            mul_g = self.mul_node_value(select_g, float(buffer_size))
            map_g = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER)
            map_g.set_input('data', rpr_buffer)
            map_g.set_input('uv', mul_g)

            select_b = self.get_y_node_value(in_col)
            mul_b = self.mul_node_value(select_b, float(buffer_size))
            map_b = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER)
            map_b.set_input('data', rpr_buffer)
            map_b.set_input('uv', mul_b)

            # combine
            out_col = self.combine_node_value(map_r, map_g, map_b)
        else:
            # just eval value
            in_col = self.get_input_default('Color')
            out_col = tuple(self.node.mapping.curves[i].evaluate(in_col[i]) for i in range(4))
            
        return self.blend_node_value(in_col, out_col, fac)


class ShaderNodeTexNoise(NodeParser):
    """Create RPR Noise node"""
    def export(self):
        scale = self.get_input_value('Scale')
        scale_rpr = self.mul_node_value(scale, 0.6)  # RPR Noise texture visually is about 60% of Blender Noise

        mapping = self.get_input_link('Vector')
        if mapping is None:  # use default mapping if no external mapping nodes attached
            mapping = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP)
            mapping.set_input('value', pyrpr.MATERIAL_NODE_LOOKUP_UV)

        uv = self.mul_node_value(scale_rpr, mapping)

        noise = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_NOISE2D_TEXTURE)
        noise.set_input('uv', uv)

        return noise


class ShaderNodeMapping(NodeParser):
    """Creating mix of lookup and math nodes to adjust texture coordinates mapping in a way Cycles do"""

    def export(self):
        mapping = self.get_input_link('Vector')
        if not mapping:
            mapping = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP)
            mapping.set_input('value', pyrpr.MATERIAL_NODE_LOOKUP_UV)

        # apply position
        offset = self.node.translation
        if not (math.isclose(offset.x, 0.0) and math.isclose(offset.y, 0.0)):
            mapping = self.sub_node_value(mapping, offset[:])

        # apply rotation, Z axis only
        angle = self.node.rotation[2]  # Blender Mapping node angle is already in radians
        if angle:
            part1 = self.dot3_node_value(mapping, (math.cos(angle), math.sin(angle), 0.0))
            part2 = self.dot3_node_value(mapping, (-math.sin(angle), math.cos(angle), 0.0))
            mapping = self.combine_node_value(part1, part2, (1.0, 1.0, 1.0))

        # apply scale
        scale = list(self.node.scale)
        if not (math.isclose(scale[0], 1.0) and math.isclose(scale[1], 1.0) and not (math.isclose(scale[2], 1.0))):
            mapping = self.mul_node_value(mapping, tuple(scale))

        if self.node.use_min:
            mapping = self.min_node_value(mapping, tuple(self.node.min))

        if self.node.use_max:
            mapping = self.max_node_value(mapping, tuple(self.node.min))

        return mapping


class ShaderNodeRGBToBW(NodeParser):
    """Convert input color or texture from RGB to grayscale colors"""

    def export(self):
        link = self.get_input_link('Color')
        if link:
            red_val = self.mul_node_value(self.get_x_node_value(link),
                                          (RED_GRAYSCALE_COEF, RED_GRAYSCALE_COEF, RED_GRAYSCALE_COEF, 0.0))
            green_val = self.mul_node_value(self.get_y_node_value(link),
                                            (GREEN_GRAYSCALE_COEF, GREEN_GRAYSCALE_COEF, GREEN_GRAYSCALE_COEF, 0.0))
            blue_val = self.mul_node_value(self.get_z_node_value(link),
                                           (BLUE_GRAYSCALE_COEF, BLUE_GRAYSCALE_COEF, BLUE_GRAYSCALE_COEF, 0.0))
            alpha_val = self.mul_node_value(self.get_w_node_value(link), (0.0, 0.0, 0.0, 1.0))
            res = self.add_node_value(red_val, green_val)
            res = self.add_node_value(res, blue_val)
            res = self.add_node_value(res, alpha_val)
            return res

        color = self.get_input_default('Color')
        val = color[0] * RED_GRAYSCALE_COEF + color[1] * GREEN_GRAYSCALE_COEF + color[2] * BLUE_GRAYSCALE_COEF
        return (val, val, val, color[3])


class ShaderNodeCombineXYZ(NodeParser):
    """ Combine 3 input values to vector/color (v1, v2, v3, 0.0), accept input maps """
    def export(self):
        value1 = self.get_input_value('X')
        value2 = self.get_input_value('Y')
        value3 = self.get_input_value('Z')

        return self.combine_node_value(value1, value2, value3)


class ShaderNodeCombineRGB(NodeParser):
    """ Combine 3 input values to vector/color (v1, v2, v3, 0.0), accept input maps """
    def export(self):
        value1 = self.get_input_value('R')
        value2 = self.get_input_value('G')
        value3 = self.get_input_value('B')

        return self.combine_node_value(value1, value2, value3)


class ShaderNodeSeparateRGB(NodeParser):
    """ Split input value(color) to 3 separate values by R-G-B channels """
    def export(self):
        value = self.get_input_value(0)

        if self.socket_out.name == 'R':
            return self.get_x_node_value(value)
        if self.socket_out.name == 'G':
            return self.get_y_node_value(value)
        return self.get_z_node_value(value)


class ShaderNodeSeparateXYZ(NodeParser):
    """ Split input value(vector) to 3 separate values by X-Y-Z channels """
    def export(self):
        value = self.get_input_value(0)

        if self.socket_out.name == 'X':
            return self.get_x_node_value(value)
        if self.socket_out.name == 'Y':
            return self.get_y_node_value(value)
        return self.get_z_node_value(value)


##
# Node Group is the material tree hidden under the ShaderNodeGroup node, with GroupInput and GroupOutput nodes.
# To parse it we have to save group node reference, walk in, parse everything inside.
# If any link goes to GroupInput socket we have to walk out via stored group node reference and find linked node.

class ShaderNodeGroup(NodeParser):
    """ Parse Group Node: find nested GroupOutput and walk from there  """
    def export(self):
        # Group Node has node tree nested, to parse it we need to find active group output node
        # that mirrors internal inputs to external outputs. Sockets have exactly the same position, name and identifier
        # 1. find inside output node
        output_node = next(
            (
                node for node in self.node.node_tree.nodes
                if node.type == 'GROUP_OUTPUT' and node.is_active_output
            ),
            None
        )

        # raise error if user has removed active group output node
        if not output_node:
            raise MaterialError("Group has no output", self.node, self.material, self.group_nodes)

        # 2. find mirrored socket by socket identifier
        socket_in = next(
            entry for entry in output_node.inputs if entry.identifier == self.socket_out.identifier
        )

        # 3. Create parser, store group node reference in parser to walk out of group
        if socket_in.is_linked:
            link = socket_in.links[0]

            if not self.is_link_allowed(link):
                raise MaterialError("Invalid link found",
                                    link, socket_in, self.node, self.material, self.group_nodes)

            # store group node for linked node parser to walk out
            return self._export_node(link.from_node, link.from_socket, group_node=self.node)

        # Ignore group output sockets with default value
        return None


class NodeGroupInput(NodeParser):
    """
    Internal group node contains incoming links.
    Walk out of the group, parse the link if requested socket linked, otherwise check for default value
    """
    def export(self):
        # The GroupNode input sockets are mirrored by GroupInput outputs with the same identifier, name and position
        # find mirrored socket by identifier
        socket_in = next(
            entry for entry in self.group_nodes[-1].inputs
            if entry.identifier == self.socket_out.identifier
        )

        if socket_in.is_linked:
            link = socket_in.links[0]

            if not self.is_link_allowed(link):
                raise MaterialError("Invalid link found",
                                    link, socket_in, self.node, self.material, self.group_nodes)

            # going out of the group, drop the containing group node info
            self.group_nodes = self.group_nodes[:-1]
            return self._export_node(link.from_node, link.from_socket)

        # Some sockets can have no default value. Check if we got one
        if hasattr(socket_in, 'default_value'):
            return self._parse_val(socket_in.default_value)

        return None


class ShaderNodeUVMap(NodeParser):
    """
    Placeholder to support new material preview mode 'cloth'

    Allow usage of UV maps other than primary. UV name passed in uv_map.
    For RPR usage this node need to know the name of base UV map of Object it assigned to.
    This way it will be able to return LOOKUP.UV or LOOKUP.UV1 for each user Object.
    """
    def export(self):
        """ Check if uv_map is set to primary, use LOOKUP node to set it """
        # The material preview uv_map value is surprisingly empty
        if not self.node.uv_map:
            uv = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP)
            uv.set_input('value', pyrpr.MATERIAL_NODE_LOOKUP_UV)
            return uv

        log.warn("Only primary mesh UV map supported", self.node.uv_map, self.node, self.material)
        return None


class ShaderNodeVolumePrincipled(NodeParser):
    def export(self):
        # TODO: implement more correct ShaderNodeVolumePrincipled

        color = self.get_input_value('Color')
        if not isinstance(color, tuple):
            color = self.get_input_default('Color')

        density = self.get_input_value('Density')
        if not isinstance(density, (float, tuple)):
            density = self.get_input_default('Density')
        if isinstance(density, tuple):
            density = density[0]

        emission = self.get_input_value('Emission Strength')
        if not isinstance(emission, (float, tuple)):
            emission = self.get_input_default('Emission Strength')
        if isinstance(emission, tuple):
            emission = emission[0]

        emission_color = self.get_input_value('Emission Color')
        if not isinstance(emission_color, tuple):
            emission_color = self.get_input_default('Emission Color')

        return {
            'color': color,
            'density': density,
            'emission': emission,
            'emission_color': emission_color,
        }
