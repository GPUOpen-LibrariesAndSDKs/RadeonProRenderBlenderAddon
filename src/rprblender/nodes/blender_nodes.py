"""
All parser classes should:
- override NodeParser with export() method
- override RuleNodeParser with class field: node
"""

import math

from .node_parser import NodeParser, RuleNodeParser
import pyrpr
import pyrprx

from rprblender.export import image
from rprblender.utils.conversion import convert_kelvins_to_rgb

from rprblender.utils import logging
log = logging.Log(tag='material')


''' TODO NODES:
    ShaderNodeMath
    ShaderNodeUVMap
    ShaderNodeAttribute
    ShaderNodeRGBCurve
    NodeGroups
    ShaderNodeHueSaturation
    ShaderNodeValToRGB
'''


ERROR_OUTPUT_COLOR = (0.0, 0.0, 0.0, 1.0)   # Corresponds Cycles error output color
ERROR_IMAGE_COLOR = (1.0, 0.0, 1.0, 1.0)    # Corresponds Cycles error image color
COLOR_GAMMA = 2.2
SSS_MIN_RADIUS = 0.0001


class ShaderNodeOutputMaterial(NodeParser):
    # inputs: Surface, Volume, Displacement

    def export(self, input_socket_key='Surface'):
        rpr_node = self.get_input_link(input_socket_key)
        if not rpr_node:
            if input_socket_key == 'Surface':
                # creating error shader
                rpr_node = self.rpr_context.create_material_node(self.node_key, pyrpr.MATERIAL_NODE_PASSTHROUGH)
                rpr_node.set_input('color', ERROR_OUTPUT_COLOR)

        return rpr_node


class ShaderNodeAmbientOcclusion(NodeParser):
    # inputs: Color, Distance

    def export(self):
        radius = self.get_input_value('Distance')
        side = (-1.0, 0.0, 0.0, 0.0) if self.node.inside else (1.0, 0.0, 0.0, 0.0)

        ao_map = self.rpr_context.create_material_node(self.node_key, pyrpr.MATERIAL_NODE_AO_MAP)
        ao_map.set_input('radius', radius)
        ao_map.set_input('side', side)

        # TODO: Properties samples, only_local, Normal input are not used yet

        if self.socket_out.name == 'AO':
            return ao_map

        color = self.get_input_value('Color')
        rpr_node = self.mul_node_value(color, ao_map, use_key=True)
        return rpr_node


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
                "normal": "link:inputs.Normal"
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
                "normal": "link:inputs.Normal"
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
                "normal": "link:inputs.Normal",
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
                "normal": "link:inputs.Normal"
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
                "normal": "link:inputs.Normal",
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
                "normal": "link:inputs.Normal"
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
                pyrprx.UBER_MATERIAL_DIFFUSE_NORMAL: "link:inputs.Normal",
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
        "Emission": {
            "type": pyrpr.MATERIAL_NODE_EMISSIVE,
            "params": {
                "color": "nodes.emission_color"
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
                "normal": "link:inputs.Normal"
            }
        }
    }


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
                pyrprx.UBER_MATERIAL_DIFFUSE_NORMAL: "link:inputs.Normal"
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
            vector = self.rpr_context.create_material_node(None, pyrpr.MATERIAL_NODE_INPUT_LOOKUP)
            vector.set_input('value', pyrpr.MATERIAL_NODE_LOOKUP_UV)

        uv = self.mul_node_value(scale_rpr, vector)

        checker = self.rpr_context.create_material_node(self.node_key, pyrpr.MATERIAL_NODE_CHECKER_TEXTURE)
        checker.set_input('uv', uv)

        if self.socket_out.name == 'Fac':
            return checker

        color1 = self.get_input_value('Color1')
        color2 = self.get_input_value('Color2')
        blend = self.blend_node_value(color1, color2, checker, use_key=True)
        return blend


class ShaderNodeTexImage(NodeParser):
    def export(self):
        if not self.node.image:
            return ERROR_IMAGE_COLOR if self.socket_out.name == 'Color' else ERROR_IMAGE_COLOR[3]

        rpr_image = image.sync(self.rpr_context, self.node.image)

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

        rpr_node = self.rpr_context.create_material_node(self.node_key, pyrpr.MATERIAL_NODE_IMAGE_TEXTURE)
        rpr_node.set_input('data', rpr_image)

        vector = self.get_input_link('Vector')
        if vector is not None:
            rpr_node.set_input('uv', vector)

        if self.socket_out.name == 'Alpha':
            rpr_node = self.arithmetic_node_value(rpr_node, None, pyrpr.MATERIAL_NODE_OP_SELECT_W, use_key=True)

        if self.node.color_space == 'COLOR':
            rpr_node = self.arithmetic_node_value(rpr_node, COLOR_GAMMA, pyrpr.MATERIAL_NODE_OP_POW, use_key=True)

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
            clearcoat_normal = self.get_input_link('Clearcoat Normal')

        ior = self.get_input_value('IOR')

        transmission = self.get_input_value('Transmission')
        transmission_roughness = None
        if enabled(transmission):
            transmission_roughness = self.get_input_value('Transmission Roughness')

        normal = self.get_input_link('Normal')

        # TODO: use Tangent input

        # Creating uber material and set inputs to it
        rpr_node = self.rpr_context.create_x_material_node(self.node_key, pyrprx.MATERIAL_UBER)

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

        rpr_node = self.rpr_context.create_material_node(self.node_key, pyrpr.MATERIAL_NODE_ADD)
        rpr_node.set_input('color0', shader1)
        rpr_node.set_input('color1', shader2)
        return rpr_node


class ShaderNodeTexCoord(RuleNodeParser):
    # outputs: Generated, Normal, UV, Objectm Camera, Window, Reflection
    # Supported outputs by RPR: Normal, UV

    nodes = {
        "Generated": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                "value": pyrpr.MATERIAL_NODE_LOOKUP_UV,
            },
            "warn": "TexCoord Generated output is not unsupported, UV will be used"
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
            "warn": "TexCoord Object output is not unsupported, world coordinate will be used"
        }

    }


class ShaderNodeLightFalloff(NodeParser):
    ''' we don't actually do light falloff in RPR.  
        So we're mainly going to pass through "strength" '''
    def export(self):
        log.warn("Light Falloff node is not supported, only strength will be taken", self.node, self.material)
        return self.get_input_default('Strength')


class ShaderNodeMixRGB(NodeParser):

    def export(self):
        fac = self.get_input_value('Fac')
        color1 = self.get_input_value('Color1')
        color2 = self.get_input_value('Color2')

        # these mix types are copied from cycles OSL
        blend_type = self.node.blend_type
        if blend_type in ('MIX', 'COLOR'):
            rpr_node = self.blend_node_value(color1, color2, fac, use_key=True)

        elif blend_type == 'ADD':
            add = self.add_node_value(color1, color2)
            rpr_node = self.blend_node_value(color1, add, fac, use_key=True)

        elif blend_type == 'MULTIPLY':
            mul = self.mul_node_value(color1, color2)
            rpr_node = self.blend_node_value(color1, mul, fac, use_key=True)

        elif blend_type == 'SUBTRACT':
            sub = self.sub_node_value(color1, color2)
            rpr_node = self.blend_node_value(color1, sub, fac, use_key=True)

        elif blend_type == 'DIVIDE':
            div = self.arithmetic_node_value(color1, color2, pyrpr.MATERIAL_NODE_OP_DIV)
            rpr_node = self.blend_node_value(color1, div, fac, use_key=True)

        elif blend_type == 'DIFFERENCE':
            sub = self.sub_node_value(color1, color2)
            abs = self.arithmetic_node_value(sub, None, pyrpr.MATERIAL_NODE_OP_ABS)
            rpr_node = self.blend_node_value(color1, abs, fac, use_key=True)

        elif blend_type == 'DARKEN':
            min_val = self.min_node_value(color1, color2)
            rpr_node = self.blend_node_value(color1, min_val, fac, use_key=True)

        elif blend_type == 'VALUE':
            rpr_node = color1

        else:
            # TODO: finish other mix types: SATURATION, HUE, LINEAR_LIGHT, SOFT_LIGHT, OVERLAY, DODGE, SCREEN, LIGHTEN, BURN
            log.warn("Ignoring unsupported Blend Type", blend_type, self.node, self.material)
            return None

        if self.node.use_clamp:
            rpr_node = self.max_node_value(self.min_node_value(rpr_node, 1.0), 0.0, use_key=True)

        return rpr_node


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
                return self.rpr_context.create_material_node(self.node_key, pyrpr.MATERIAL_NODE_DIFFUSE)

        shader1 = self.get_input_link(1)
        shader2 = self.get_input_link(2)

        rpr_node = self.rpr_context.create_material_node(self.node_key, pyrpr.MATERIAL_NODE_BLEND)
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

        rpr_node = self.rpr_context.create_material_node(self.node_key, pyrpr.MATERIAL_NODE_NORMAL_MAP)
        rpr_node.set_input('color', color)
        rpr_node.set_input('bumpscale', strength)

        if self.node.space != 'TANGENT':
            log.warn("Ignoring unsupported normal map space", self.node.space, self.node, self.material)

        if self.node.uv_map:
            log.warn("Ignoring unsupported normal map uv_map", self.node.uv_map, self.node, self.material)

        return rpr_node


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

        rpr_node = self.rpr_context.create_material_node(self.node_key, pyrpr.MATERIAL_NODE_BUMP_MAP)
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
    """Return RGB color by blackbody temperature"""

    def export(self):
        temperature = self.get_input_default('Temperature')
        return convert_kelvins_to_rgb(temperature)


class ShaderNodeTexNoise(NodeParser):
    """Create RPR Noise node"""
    def export(self):
        scale = self.get_input_value('Scale')
        scale_rpr = self.mul_node_value(scale, 0.6)  # RPR Noise texture visually is about 60% of Blender Noise

        mapping = self.get_input_link('Vector')
        if mapping is None:  # use default mapping if no external mapping nodes attached
            mapping = self.rpr_context.create_material_node(None, pyrpr.MATERIAL_NODE_INPUT_LOOKUP)
            mapping.set_input('value', pyrpr.MATERIAL_NODE_LOOKUP_UV)

        uv = self.mul_node_value(scale_rpr, mapping)

        noise = self.rpr_context.create_material_node(self.node_key, pyrpr.MATERIAL_NODE_NOISE2D_TEXTURE)
        noise.set_input('uv', uv)

        return noise


class ShaderNodeMapping(NodeParser):
    """Creating mix of lookup and math nodes to adjust texture coordinates mapping in a way Cycles do"""

    def export(self):
        mapping = self.get_input_link('Vector')
        if not mapping:
            mapping = self.rpr_context.create_material_node(None, pyrpr.MATERIAL_NODE_INPUT_LOOKUP)
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
        if not (math.isclose(scale[0], 1.0) and math.isclose(scale[1], 1.0)):
            scale[0] = 1/scale[0] if not math.isclose(math.fabs(scale[0]), 0.0) else 0.0
            scale[1] = 1/scale[1] if not math.isclose(math.fabs(scale[0]), 0.0) else 0.0
            mapping = self.mul_node_value(mapping, tuple(scale))

        return mapping


class ShaderNodeRGBToBW(NodeParser):
    """Convert input color or texture from RGB to grayscale colors"""

    def export(self):
        link = self.get_input_link('Color')
        if link:
            r_val = self.mul_node_value(self.get_x_node_value(link), (0.2126, 0.2126, 0.2126, 0.0))
            g_val = self.mul_node_value(self.get_y_node_value(link), (0.7152, 0.7152, 0.7152, 0.0))
            b_val = self.mul_node_value(self.get_z_node_value(link), (0.0722, 0.0722, 0.0722, 0.0))
            a_val = self.mul_node_value(self.get_w_node_value(link), (0.0, 0.0, 0.0, 1.0))
            res = self.add_node_value(r_val, g_val)
            res = self.add_node_value(res, b_val)
            res = self.add_node_value(res, a_val)
            return res

        color = self.get_input_default('Color')
        val = color[0] * 0.2126 + color[1] * 0.7152 + color[2] * 0.0722
        return (val, val, val, color[3])

