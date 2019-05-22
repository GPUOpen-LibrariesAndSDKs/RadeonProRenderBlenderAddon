"""
All parser classes should:
- override NodeParser with export() method
- override RuleNodeParser with class field: node
"""

import math
import numpy as np

from .node_parser import NodeParser, RuleNodeParser, MaterialError, get_node_parser_class
from .node_item import NodeItem
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


class ShaderNodeOutputMaterial(NodeParser):
    # inputs: Surface, Volume, Displacement

    def export(self, input_socket_key):
        node_item = self.get_input_link(input_socket_key)
        if not node_item:
            if input_socket_key == 'Surface':
                # checking if we have connected node to Volume socket
                volume_rpr_node = self.get_input_link('Volume')
                if volume_rpr_node:
                    rpr_node = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_TRANSPARENT)
                    rpr_node.set_input('color', (1.0, 1.0, 1.0))
                else:
                    raise MaterialError("Empty Surface input socket", self.node, self.material)

        return node_item

    def final_export(self, input_socket_key='Surface'):
        try:
            return self.export(input_socket_key)()
        except MaterialError as e:  # material nodes setup error, stop parsing and inform user
            log.error(e)
            # creating error shader
            return self.create_node(pyrpr.MATERIAL_NODE_PASSTHROUGH, {'color': ERROR_OUTPUT_COLOR})
            

class ShaderNodeAmbientOcclusion(NodeParser):
    # inputs: Color, Distance

    def export(self):
        radius = self.get_input_value('Distance')
        side = (-1.0, 0.0, 0.0, 0.0) if self.node.inside else (1.0, 0.0, 0.0, 0.0)

        ao_map = self.create_node(pyrpr.MATERIAL_NODE_AO_MAP, {'radius': radius, 'side': side})

        if self.socket_out.name == 'AO':
            return ao_map

        color = self.get_input_value('Color')
        
        return color * ao_map
        

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
        "Color": {  # output
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

    nodes = {
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
            normal = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, params={'value': pyrpr.MATERIAL_NODE_LOOKUP_N})

        I = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, params={'value': pyrpr.MATERIAL_NODE_LOOKUP_INVEC})
        IdotN = I.dot(normal)
        
        if self.socket_out.name == 'Fresnel':
            # backfacing if I.N < 0
            backfacing = IdotN < 0.0

            eta = NodeItem.max((1.0 - blend), 0.00001)
            # if not backfacing eta = 1/eta
            eta2 = NodeItem.if_else(backfacing, eta, 1.0/eta)
            
            fresnel = self.create_node(pyrpr.MATERIAL_NODE_FRESNEL, params={'normal': normal, 'ior': eta2})
            return fresnel

        else:
            # Facing input
            blend2 = blend.clamp(0.0, .99999)
            blend_less_than_half = blend2 < 0.5
            blend3 = NodeItem.if_else(blend_less_than_half, (blend2 * 2.0), (0.5 / (1.0 - blend2)))

            abs_IdotN = abs(IdotN)
            facing = abs_IdotN ** blend3
            return (1.0 - facing)


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
        scale_rpr = scale * 0.125  # in RPR it is divided by 8 (or multiplied by 0.125)

        vector = self.get_input_link('Vector')
        if vector is None:
            vector = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, params={'value': pyrpr.MATERIAL_NODE_LOOKUP_UV})

        uv = scale_rpr * vector

        checker = self.create_node(pyrpr.MATERIAL_NODE_CHECKER_TEXTURE, params={'uv': uv})

        if self.socket_out.name == 'Fac':
            return checker

        color1 = self.get_input_value('Color1')
        color2 = self.get_input_value('Color2')
        blend = NodeItem.blend(color1, color2, checker)
        return blend


class ShaderNodeTexImage(NodeParser):
    def export(self):
        if not self.node.image:
            return NodeItem(self.rpr_context, ERROR_IMAGE_COLOR) if self.socket_out.name == 'Color' else NodeItem(self.rpr_context, ERROR_IMAGE_COLOR[3])

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
        if self.node.color_space == 'COLOR':
            rpr_image.set_gamma(COLOR_GAMMA)

        # TODO: Implement using node properties: interpolation, projection
        if self.node.interpolation != 'Linear':
            log.warn("Ignoring unsupported texture interpolation", self.node.interpolation, self.node, self.material)
        if self.node.projection != 'FLAT':
            log.warn("Ignoring unsupported texture projection", self.node.projection, self.node, self.material)

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, params={'data': rpr_image})

        vector = self.get_input_link('Vector')
        if vector is not None:
            rpr_node.set_input('uv', vector)

        if self.socket_out.name == 'Alpha':
            rpr_node = rpr_node['a']

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
        rpr_node = self.create_uber()

        diffuse = 1.0 - transmission # TODO: this has to be checked
        
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
            subsurface_radius = NodeItem.max(subsurface_radius, SSS_MIN_RADIUS)
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

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_ADD, params={'color0': shader1, 'color1': shader2})
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
        if blend_type  == 'MIX':
            rpr_node = NodeItem.blend(color1, color2, fac)

        elif blend_type == 'ADD':
            rpr_node = NodeItem.blend(color1, color1 + color2, fac)

        elif blend_type == 'MULTIPLY':
            rpr_node = NodeItem.blend(color1, color1 * color2, fac)

        elif blend_type == 'SCREEN':
            rpr_node = 1.0 - (1.0 - fac + fac * (1.0 - color2) * (1.0 - color1))

        elif blend_type == 'OVERLAY':
            t = fac
            tm = 1.0 - fac
            
            rpr_node = NodeItem.if_else(color1 < 0.5, 
                                    color1 * (tm + 2.0 * t * color2),
                                    1.0 - (tm + 2.0 * t * (1.0 - color2)) * (1.0 - color1))
    
        elif blend_type == 'SUBTRACT':
            rpr_node = NodeItem.blend(color1, color1 - color2, fac)

        elif blend_type == 'DIVIDE':
            rpr_node = NodeItem.blend(color1, color1 / color2, fac)

        elif blend_type == 'DIFFERENCE':
            rpr_node = NodeItem.blend(color1, abs(color1 - color2), fac)

        elif blend_type == 'DARKEN':
            rpr_node = NodeItem.blend(color1, NodeItem.min(color1, color2), fac)

        elif blend_type == 'LIGHTEN':
            rpr_node = NodeItem.max(color1, color2 * fac)

        elif blend_type == 'DODGE':
            tmp = 1.0 - (fac * color2)
            tmp2 = color1 / tmp
            
            if1 = NodeItem.if_else(tmp2 > 1.0, 1.0, tmp)
            if2 = NodeItem.if_else(tmp <= 0.0, 1.0, if1)
            rpr_node = NodeItem.if_else(color1 != 0.0, if2, color1)
        
        elif blend_type == 'BURN':
            tm = 1.0 - fac
            tmp = tm + fac * color2
            tmp2 = color1 / tmp

            if1 = NodeItem.if_else(tmp2 > 1.0, 1.0, tmp2)
            if2 = NodeItem.if_else(tmp2 < 0.0, 0.0, if1)
            rpr_node = NodeItem.if_else(tmp <= 0.0, 0.0, color1)
        
        elif blend_type == 'HUE':
            hsv2 = color2.rgb_to_hsv()
            hsv1 = color1.rgb_to_hsv()
            hsv1_2 = hsv1.set_channel(0, hsv2[0])
            blend = NodeItem.blend(color1, hsv1_2.hsv_to_rgb(), fac)

            rpr_node = NodeItem.if_else(hsv2[1] != 0.0, blend, color1)

        elif blend_type == 'SATURATION':
            hsv2 = color2.rgb_to_hsv()
            hsv1 = color1.rgb_to_hsv()
            hsv1_2 = hsv1.set_channel(1, NodeItem.blend(hsv1[1], hsv2[1], fac))
            
            rpr_node = NodeItem.if_else(hsv1[1] != 0.0, hsv1_2.hsv_to_rgb(), color1)

        elif blend_type == 'VALUE':
            hsv2 = color2.rgb_to_hsv()
            hsv1 = color1.rgb_to_hsv()
            hsv1_2 = hsv1.set_channel(2, NodeItem.blend(hsv1[2], hsv2[2], fac))
            
            rpr_node = hsv1_2.hsv_to_rgb()

        elif blend_type == 'COLOR':
            hsv2 = color2.rgb_to_hsv()
            hsv1 = color1.rgb_to_hsv()
            hsv2_2 = hsv2.set_channel(2, hsv1[2])
            tmp = hsv2_2.hsv_to_rgb()
            
            rpr_node = NodeItem.if_else(hsv2[1] != 0.0, NodeItem.blend(color1, tmp, fac), color1)

        elif blend_type == 'SOFT_LIGHT':
            scr = 1.0 - (1.0 - color2) * (1.0 - color1)
            rpr_node = NodeItem.blend(color1, ((1.0 - color1) * color2 * color1 + color1 * scr ), fac )

        elif blend_type == 'LINEAR_LIGHT':
            col1 = color1 + fac * (2.0 * (color2 - 0.5))
            col2 = color1 + fac * (2.0 * (color2 - 1.0))
            rpr_node = NodeItem.if_else(color2 > 0.5, col1, col2)

        else:
            # TODO: finish other mix types: 
            log.warn("Ignoring unsupported Blend Type", blend_type, self.node, self.material)
            return None

        if self.node.use_clamp:
            rpr_node = rpr_node.clamp()

        return rpr_node


class ShaderNodeMath(NodeParser):
    ''' simply map the blender op types to rpr op types with included map.
        We could be more correct with "round" but I've never seen this used. '''
    # map blender node op to rpr math op and number of inputs
    

    def export(self):
        in1 = self.get_input_value(0)
        in2 = self.get_input_value(1) if len(self.node.inputs) >= 2 else None

        blender_op = self.node.operation

        if blender_op == 'ADD':
            math_node = in1 + in2
        elif blender_op == 'SUBTRACT':
            math_node = in1 - in2
        elif blender_op == 'MULTIPLY':
            math_node = in1 * in2
        elif blender_op == 'SINE':
            math_node = in1.create_arithmetic(None, pyrpr.MATERIAL_NODE_OP_SIN)
        elif blender_op == 'COSINE':
            math_node = in1.create_arithmetic(None, pyrpr.MATERIAL_NODE_OP_COS)
        elif blender_op == 'TANGENT':
            math_node = in1.create_arithmetic(None, pyrpr.MATERIAL_NODE_OP_TAN)
        elif blender_op == 'ARCSINE':
            math_node = in1.create_arithmetic(None, pyrpr.MATERIAL_NODE_OP_ASIN)
        elif blender_op == 'ARCCOSINE':
            math_node = in1.create_arithmetic(None, pyrpr.MATERIAL_NODE_OP_ACOS)
        elif blender_op == 'ARCTANGENT':
            math_node = in1.create_arithmetic(None, pyrpr.MATERIAL_NODE_OP_ATAN)
        elif blender_op == 'POWER':
            math_node = in1 ** in2
        elif blender_op == 'LOGARITHM':
            math_node = in1.create_arithmetic(None, pyrpr.MATERIAL_NODE_OP_LOG)
        elif blender_op == 'MINIMUM':
            math_node = NodeItem.min(in1, in2)
        elif blender_op == 'MAXIMUM':
            math_node = NodeItem.max(in1, in2)
        elif blender_op == 'LESS_THAN':
            math_node = in1 < in2
        elif blender_op == 'GREATER_THAN':
            math_node = in1 > in2
        elif blender_op == 'MODULO':
            math_node = in1 % in2
        elif blender_op == 'ABSOLUTE':
            math_node = abs(in1)
        elif blender_op == 'FLOOR':
            math_node = math.floor(in1)
        elif blender_op == 'SQRT':
            # use pow with 1/power
            math_node = in1 ** (1.0 / in2)
        elif blender_op == 'ARCTAN2':
            # arctan in1/in2
            math_node = in1.create_arithmetic(in2, pyrpr.MATERIAL_NODE_OP_ATAN)
        elif blender_op == 'FRACT':
            # v1 % 1.0
            math_node = in1 % 1.0
        elif blender_op == 'CEIL':
            # v1 + (1 - mod(v1, 1.0))
            math_node = in1 + (1.0 - (in1 % 1.0))
        elif blender_op == 'ROUND':
            # ceil if (v1 % 1.0 ) > .5 else floor
            fract = in1 % 1.0
            ceil = in1 + (1.0 - fract)

            math_node = NodeItem.if_else((fract > 0.5), ceil, math.floor(in1))

        # finally do clamp
        if self.node.use_clamp:
            return math_node.clamp()
        else:
            return math_node


class ShaderNodeVectorMath(NodeParser):
    """ Apply vector math operations assuming Blender node was designed to work with 3-axis vectors """
    # map blender vector math node operations to rpr math operations and number of inputs
    def export(self):
        blender_op = self.node.operation

        in1 = self.get_input_value(0)
        in2 = self.get_input_value(1)

        if blender_op == 'ADD':
            math_node = in1 + in2
        elif blender_op == 'SUBTRACT':
            math_node = in1 - in2
        elif blender_op == 'AVERAGE':
            math_node = in1.create_arithmetic(in2, pyrpr.MATERIAL_NODE_OP_AVERAGE_XYZ)
        elif blender_op == 'DOT_PRODUCT':
            math_node = in1.dot(in2)
        elif blender_op == 'DOT_PRODUCT':
            math_node = in1.create_arithmetic(in2, pyrpr.MATERIAL_NODE_OP_CROSS)
        elif blender_op == 'NORMALIZE':
            math_node = in1.create_arithmetic(None, pyrpr.MATERIAL_NODE_OP_NORMALIZE)

        if self.socket_out.name == 'Value':
            return math_node.to_bw()
        else:
            return math_node


class ShaderNodeHueSaturation(NodeParser):
    
    def export(self):
        rgb = self.get_input_value('Color')
        hsv = rgb.rgb_to_hsv()
        h = (hsv[0] + self.get_input_value('Hue')) % 1.0
        s = (hsv[1] + self.get_input_value('Saturation')).clamp()
        v = hsv[2] * self.get_input_value('Value')

        rgb2 = NodeItem.max(NodeItem.combine_node_items(h,s,v).hsv_to_rgb(), 0.0)
        return NodeItem.blend(rgb, rgb2, self.get_input_value('Fac'))


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
                return self.create_node(pyrpr.MATERIAL_NODE_DIFFUSE)

        shader1 = self.get_input_link(1)
        shader2 = self.get_input_link(2)

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_BLEND)
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

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_NORMAL_MAP)
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
            color = height * distance

        if self.node.invert:
            color = -1.0 * color

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_BUMP_MAP)
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
            math_op = (link - 1000.0) / 100.0
            
            temperature = self.create_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER)
            temperature.set_input('data', rpr_buffer)
            temperature.set_input('uv', math_op)
            return temperature
        else:
            return NodeItem(self.rpr_context, convert_kelvins_to_rgb(self.get_input_default('Temperature')))


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

            uv = link * float(buffer_size)
            read = self.create_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER)
            read.set_input('data', rpr_buffer)
            read.set_input('uv', uv)
            if self.socket_out.name == 'Alpha':
                return read['a']
            else:
                return read
        else:
            # just eval value
            val = self.node.color_ramp.evaluate(self.get_input_default('Fac'))
            if self.socket_out.name == 'Alpha':
                return NodeItem(self.rpr_context, val[3])
            else:
                return NodeItem(self.rpr_context, val)


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
            select_r = in_col['r'] * float(buffer_size)
            map_r = self.create_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER)
            map_r.set_input('data', rpr_buffer)
            map_r.set_input('uv', select_r)

            select_g = in_col['g'] * float(buffer_size)
            map_g = self.create_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER)
            map_g.set_input('data', rpr_buffer)
            map_g.set_input('uv', select_g)

            select_b = in_col['b'] * float(buffer_size)
            map_b = self.create_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER)
            map_b.set_input('data', rpr_buffer)
            map_b.set_input('uv', select_b)

            # combine
            out_col = NodeItem.combine_node_items(map_r, map_g, map_b)
        else:
            # just eval value
            in_col = self.get_input_default('Color')
            out_col = NodeItem(self.rpr_context, tuple(self.node.mapping.curves[i].evaluate(in_col[i]) for i in range(4)))
            
        return NodeItem.blend(in_col, out_col, fac)


class ShaderNodeTexNoise(NodeParser):
    """Create RPR Noise node"""
    def export(self):
        scale = self.get_input_value('Scale')
        scale_rpr = scale * 0.6# RPR Noise texture visually is about 60% of Blender Noise

        mapping = self.get_input_link('Vector')
        if mapping is None:  # use default mapping if no external mapping nodes attached
            mapping = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP)
            mapping.set_input('value', pyrpr.MATERIAL_NODE_LOOKUP_UV)

        noise = self.create_node(pyrpr.MATERIAL_NODE_NOISE2D_TEXTURE)
        noise.set_input('uv', scale_rpr * mapping)

        return noise


class ShaderNodeMapping(NodeParser):
    """Creating mix of lookup and math nodes to adjust texture coordinates mapping in a way Cycles do"""

    def export(self):
        mapping = self.get_input_link('Vector')
        if not mapping:
            mapping = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP)
            mapping.set_input('value', pyrpr.MATERIAL_NODE_LOOKUP_UV)

        # apply position
        offset = self.node.translation
        if not (math.isclose(offset.x, 0.0) and math.isclose(offset.y, 0.0) and math.isclose(offset.z, 0.0)):
            mapping = mapping - tuple(offset[:])

        # apply rotation, Z axis only
        angle = self.node.rotation[2]  # Blender Mapping node angle is already in radians
        if angle:
            part1 = mapping.dot((math.cos(angle), math.sin(angle), 0.0))
            part2 = mapping.dot((-math.sin(angle), math.cos(angle), 0.0))
            mapping = NodeItem.combine_node_items(part1, part2, NodeItem(self.rpr_context, (1.0, 1.0, 1.0)))

        # apply scale
        scale = list(self.node.scale)
        if not (math.isclose(scale[0], 1.0) and math.isclose(scale[1], 1.0) and not (math.isclose(scale[2], 1.0))):
            mapping = mapping * tuple(scale)

        if self.node.use_min:
            mapping = NodeItem.min(mapping, tuple(self.node.min))

        if self.node.use_max:
            mapping = NodeItem.max(mapping, tuple(self.node.min))

        return mapping


class ShaderNodeRGBToBW(NodeParser):
    """Convert input color or texture from RGB to grayscale colors"""

    def export(self):
        return self.get_input_value('Color').to_bw()


class ShaderNodeCombineXYZ(NodeParser):
    """ Combine 3 input values to vector/color (v1, v2, v3, 0.0), accept input maps """
    def export(self):
        value1 = self.get_input_value('X')
        value2 = self.get_input_value('Y')
        value3 = self.get_input_value('Z')

        return NodeItem.combine_node_items(value1, value2, value3)


class ShaderNodeCombineRGB(NodeParser):
    """ Combine 3 input values to vector/color (v1, v2, v3, 0.0), accept input maps """
    def export(self):
        value1 = self.get_input_value('R')
        value2 = self.get_input_value('G')
        value3 = self.get_input_value('B')

        return NodeItem.combine_node_items(value1, value2, value3)


class ShaderNodeCombineHSV(NodeParser):
    """ Combine 3 input values to vector/color (v1, v2, v3, 0.0), accept input maps """
    def export(self):
        value1 = self.get_input_value('H')
        value2 = self.get_input_value('S')
        value3 = self.get_input_value('V')

        return NodeItem.combine_node_items(value1, value2, value3).hsv_to_rgb()


class ShaderNodeSeparateRGB(NodeParser):
    """ Split input value(color) to 3 separate values by R-G-B channels """
    def export(self):
        value = self.get_input_value(0)

        return value[self.socket_out.name.lower()]


class ShaderNodeSeparateHSV(NodeParser):
    """ Split input value(color) to 3 separate values by HSV channels """
    def export(self):
        value = self.get_input_value(0).rgb_to_hsv()

        socket = {'H': 0, 'S': 1, 'V': 2}[self.socket_out.name]

        return value[socket]


class ShaderNodeSeparateXYZ(NodeParser):
    """ Split input value(vector) to 3 separate values by X-Y-Z channels """
    def export(self):
        value = self.get_input_value(0)

        return value[self.socket_out.name.lower()]


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
