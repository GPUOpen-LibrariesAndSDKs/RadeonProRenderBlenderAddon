"""
All parser classes should:
- override NodeParser with export() method
- override RuleNodeParser with class field: node
"""

import math
import numpy as np

import pyrpr

from rprblender.export import image, material
from rprblender.utils.conversion import convert_kelvins_to_rgb
from .node_parser import BaseNodeParser, RuleNodeParser, NodeParser, MaterialError
from .node_item import NodeItem

from rprblender.utils import logging
log = logging.Log(tag='export.rpr_nodes')


''' TODO NODES:
    ShaderNodeAttribute
'''


ERROR_OUTPUT_COLOR = (1.0, 0.0, 1.0, 1.0)   # Corresponds Cycles error output color
ERROR_IMAGE_COLOR = (1.0, 0.0, 1.0, 1.0)    # Corresponds Cycles error image color
COLOR_GAMMA = 2.2
SSS_MIN_RADIUS = 0.0001


class ShaderNodeOutputMaterial(BaseNodeParser):
    # inputs: Surface, Volume, Displacement

    def get_normal_node(self):
        """ Returns the normal node if displacement mode is set to bump 
            this returns a bumped normal, else returns a node_lookup N """
        if self.material.cycles.displacement_method in {"BUMP", "BOTH"}:
            displacement_input = self.get_input_link("Displacement")
            if displacement_input:
                return self.create_node(pyrpr.MATERIAL_NODE_BUMP_MAP, {
                    pyrpr.MATERIAL_INPUT_COLOR: displacement_input,
                    pyrpr.MATERIAL_INPUT_SCALE: 1.0,
                })

        return None

    def export(self, input_socket_key='Surface'):
        if input_socket_key == 'Surface':
            self.normal_node = self.get_normal_node()

        rpr_node = self.get_input_link(input_socket_key)
        if input_socket_key == 'Surface':
            if rpr_node:
                return rpr_node

            # checking if we have connected node to Volume socket
            volume_rpr_node = material.sync(self.rpr_context, self.material, 'Volume')
            if volume_rpr_node:
                return self.create_node(pyrpr.MATERIAL_NODE_TRANSPARENT, {
                    pyrpr.MATERIAL_INPUT_COLOR: (1.0, 1.0, 1.0)
                })

            raise MaterialError("Incorrect Surface input socket",
                                rpr_node, self.node, self.material)

        if input_socket_key == 'Displacement':
            return rpr_node

        if input_socket_key == 'Volume':
            if not rpr_node or rpr_node.type == pyrpr.MATERIAL_NODE_VOLUME:
                return rpr_node

            raise MaterialError("Incorrect Volume input socket",
                                rpr_node, rpr_node.type, self.node, self.material)

        raise MaterialError("Incorrect input_socket_key",
                            input_socket_key, self.node, self.material)

    def final_export(self, input_socket_key='Surface'):
        try:
            return self.export(input_socket_key)

        except MaterialError as e:  # material nodes setup error, stop parsing and inform user
            log.error(e)

            if input_socket_key == 'Surface':
                # creating error shader
                return self.create_node(pyrpr.MATERIAL_NODE_PASSTHROUGH, {
                    pyrpr.MATERIAL_INPUT_COLOR: ERROR_OUTPUT_COLOR
                })

            return None


class ShaderNodeAmbientOcclusion(NodeParser):
    # inputs: Color, Distance

    def export(self):
        radius = self.get_input_value('Distance')
        side = (-1.0, 0.0, 0.0, 0.0) if self.node.inside else (1.0, 0.0, 0.0, 0.0)

        ao_map = self.create_node(pyrpr.MATERIAL_NODE_AO_MAP, {
            pyrpr.MATERIAL_INPUT_RADIUS: radius,
            pyrpr.MATERIAL_INPUT_SIDE: side
        })

        # TODO: Properties samples, only_local, Normal input are not used yet

        if self.socket_out.name == 'AO':
            return ao_map

        color = self.get_input_value('Color')
        return ao_map * color


class ShaderNodeDisplacement(NodeParser):
    # inputs: Height, Midlevel, Scale, Normal
    
    def export(self):
        height = self.get_input_value('Height')
        midlevel = self.get_input_value('Midlevel')
        scale = self.get_input_value('Scale')
        normal = self.get_input_normal('Normal')

        # displacement vec = Scale * (Height - Midlevel) * Normal
        displacement = scale * (height - midlevel)
        if normal:
            displacement *= normal

        return displacement


class NodeReroute(NodeParser):
    # Just pass through the input

    def export(self):
        return self.get_input_link(0)


class ShaderNodeBrightContrast(NodeParser):
    # inputs: Bright, Contrast, Color

    def export(self):
        bright = self.get_input_value('Bright')
        color = self.get_input_value('Color')
        contrast = self.get_input_value('Contrast')

        # Following formula should be used:
        #   color_out = max(Bright + (Color - 0.5) * (Contrast + 1.0) + 0.5, 0.0)
        # This formula was given from OSL shader code in cycles and modified
        # to correspond to how it works in cycles
        return (bright + (color - 0.5) * (contrast + 1.0) + 0.5).max(0.0)


class ShaderNodeBsdfAnisotropic(NodeParser):
    # inputs: Color, Roughness, Anisotropy, Rotation, Normal

    def export(self):
        color = self.get_input_value('Color')
        roughness = self.get_input_value('Roughness')
        anisotropy = self.get_input_value('Anisotropy')
        rotation = self.get_input_value('Rotation')
        normal = self.get_input_normal('Normal')
        # TODO: Use Tangent input and distribution property

        rotation = 0.5 - (rotation % 1)

        result = self.create_node(pyrpr.MATERIAL_NODE_MICROFACET_ANISOTROPIC_REFLECTION, {
            pyrpr.MATERIAL_INPUT_COLOR: color,
            pyrpr.MATERIAL_INPUT_ROUGHNESS: roughness * roughness,
            pyrpr.MATERIAL_INPUT_ANISOTROPIC: anisotropy,
            pyrpr.MATERIAL_INPUT_ROTATION: rotation,
        })
        if normal:
            result.set_input(pyrpr.MATERIAL_INPUT_NORMAL, normal)

        return result

    def export_hybrid(self):
        color = self.get_input_value('Color')
        roughness = self.get_input_value('Roughness')
        anisotropy = self.get_input_value('Anisotropy')
        rotation = self.get_input_value('Rotation')
        normal = self.get_input_normal('Normal')
        # TODO: Use Tangent input and distribution property

        rotation = 0.5 - (rotation % 1)

        result = self.create_node(pyrpr.MATERIAL_NODE_UBERV2, {
            pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_WEIGHT: 0.0,
            pyrpr.UBER_MATERIAL_INPUT_REFLECTION_COLOR: color,
            pyrpr.UBER_MATERIAL_INPUT_REFLECTION_ROUGHNESS: roughness * roughness,
            pyrpr.UBER_MATERIAL_INPUT_REFLECTION_ANISOTROPY: anisotropy,
            pyrpr.UBER_MATERIAL_INPUT_REFLECTION_ANISOTROPY_ROTATION: rotation,
        })
        if normal:
            result.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_NORMAL, normal)

        return result


class ShaderNodeBsdfDiffuse(RuleNodeParser):
    # inputs: Color, Roughness, Normal

    nodes = {
        "square_roughness": {
            "type": "*",
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR0: "inputs.Roughness",
                pyrpr.MATERIAL_INPUT_COLOR1: "inputs.Roughness",
            }
        },

        "BSDF": {
            "type": pyrpr.MATERIAL_NODE_DIFFUSE,
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR: "inputs.Color",
                pyrpr.MATERIAL_INPUT_ROUGHNESS: "nodes.square_roughness",
                pyrpr.MATERIAL_INPUT_NORMAL: "normal:inputs.Normal"
            }
        },

        'hybrid:BSDF': {
            'type': pyrpr.MATERIAL_NODE_UBERV2,
            'params': {
                pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_WEIGHT: 1.0,
                pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_COLOR: 'inputs.Color',
                pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_ROUGHNESS: 'nodes.square_roughness',
                pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_NORMAL: 'normal:inputs.Normal',
            }
        }
    }


class ShaderNodeBsdfGlass(NodeParser):
    # inputs: Color, Roughness, Normal, IOR

    def export(self):
        def enabled(val: [NodeItem, None]):
            if val is None:
                return False

            if isinstance(val.data, float) and math.isclose(val.data, 0.0):
                return False

            if isinstance(val.data, tuple) and \
               math.isclose(val.data[0], 0.0) and \
               math.isclose(val.data[1], 0.0) and \
               math.isclose(val.data[2], 0.0):
                return False

            return True

        # Getting require inputs. Note: if some inputs are not needed they won't be taken
        base_color = self.get_input_value('Color')
        roughness = self.get_input_value('Roughness')
        ior = self.get_input_value('IOR')
        normal = self.get_input_normal('Normal')

        # Creating uber material and set inputs to it
        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_UBERV2)

        # disable diffuse
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_WEIGHT, 0.0)
        
        # reflection
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_WEIGHT, 1.0)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_MODE,
                                   pyrpr.UBER_MATERIAL_IOR_MODE_PBR)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_IOR, ior)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_COLOR, base_color)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_ROUGHNESS, roughness * roughness)

        # refraction 
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFRACTION_WEIGHT, 1.0)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFRACTION_COLOR, base_color)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFRACTION_ROUGHNESS, roughness * roughness)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFRACTION_IOR, ior)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFRACTION_THIN_SURFACE, False)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFRACTION_CAUSTICS, True)

        if enabled(normal):
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFRACTION_NORMAL, normal)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_NORMAL, normal)

        return rpr_node


class ShaderNodeBsdfGlossy(RuleNodeParser):
    # inputs: Color, Roughness, Normal

    nodes = {
        "square_roughness": {
            "type": "*",
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR0: "inputs.Roughness",
                pyrpr.MATERIAL_INPUT_COLOR1: "inputs.Roughness",
            }
        },

        "BSDF": {
            "type": pyrpr.MATERIAL_NODE_MICROFACET,
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR: "inputs.Color",
                pyrpr.MATERIAL_INPUT_ROUGHNESS: "nodes.square_roughness",
                pyrpr.MATERIAL_INPUT_NORMAL: "normal:inputs.Normal"
            }
        },
        "hybrid:BSDF": {
            "type": pyrpr.MATERIAL_NODE_UBERV2,
            "params": {
                pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_WEIGHT: 0.0,
                pyrpr.UBER_MATERIAL_INPUT_REFLECTION_WEIGHT: 1.0,
                pyrpr.UBER_MATERIAL_INPUT_REFLECTION_COLOR: "inputs.Color",
                pyrpr.UBER_MATERIAL_INPUT_REFLECTION_ROUGHNESS: "nodes.square_roughness",
                pyrpr.UBER_MATERIAL_INPUT_REFLECTION_NORMAL: "normal:inputs.Normal",
            }
        }

    }
    # TODO: Use distribution property


class ShaderNodeBsdfRefraction(RuleNodeParser):
    # inputs: Color, Roughness, Normal, IOR

    nodes = {
        "square_roughness": {
            "type": "*",
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR0: "inputs.Roughness",
                pyrpr.MATERIAL_INPUT_COLOR1: "inputs.Roughness",
            }
        },

        "BSDF": {
            "type": pyrpr.MATERIAL_NODE_MICROFACET_REFRACTION,
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR: "inputs.Color",
                pyrpr.MATERIAL_INPUT_ROUGHNESS: "nodes.square_roughness",
                pyrpr.MATERIAL_INPUT_NORMAL: "normal:inputs.Normal",
                pyrpr.MATERIAL_INPUT_IOR: "inputs.IOR"
            }
        },
        "hybrid:BSDF": {
            "type": pyrpr.MATERIAL_NODE_UBERV2,
            "params": {
                pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_WEIGHT: 0.0,
                pyrpr.UBER_MATERIAL_INPUT_REFRACTION_WEIGHT: 1.0,
                pyrpr.UBER_MATERIAL_INPUT_REFRACTION_COLOR: "inputs.Color",
                pyrpr.UBER_MATERIAL_INPUT_REFRACTION_ROUGHNESS: "nodes.square_roughness",
                pyrpr.UBER_MATERIAL_INPUT_REFRACTION_NORMAL: "normal:inputs.Normal",
                pyrpr.UBER_MATERIAL_INPUT_REFRACTION_IOR: "inputs.IOR"
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
                pyrpr.MATERIAL_INPUT_COLOR: "inputs.Color",
                pyrpr.MATERIAL_INPUT_NORMAL: "normal:inputs.Normal"
            }
        },
        "hybrid:BSDF": {
            "type": pyrpr.MATERIAL_NODE_UBERV2,
            "params": {
                pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_WEIGHT: 1.0,
                pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_COLOR: "inputs.Color",
                pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_NORMAL: "normal:inputs.Normal",
                pyrpr.UBER_MATERIAL_INPUT_REFRACTION_WEIGHT: 1.0,
                pyrpr.UBER_MATERIAL_INPUT_REFRACTION_COLOR: "inputs.Color",
                pyrpr.UBER_MATERIAL_INPUT_REFRACTION_NORMAL: "normal:inputs.Normal",
            }
        }
    }


class ShaderNodeBsdfTransparent(NodeParser):
    # inputs: Color

    def export(self):
        color = self.get_input_value('Color')
        return self.create_node(pyrpr.MATERIAL_NODE_TRANSPARENT, {
            pyrpr.MATERIAL_INPUT_COLOR: color
        })

    def export_hybrid(self):
        color = self.get_input_value('Color')
        return self.create_node(pyrpr.MATERIAL_NODE_UBERV2, {
            pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_WEIGHT: 1.0,
            pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_ROUGHNESS: 0.0,
            pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_COLOR: color,
            pyrpr.UBER_MATERIAL_INPUT_TRANSPARENCY: color.average_xyz(),
        })


class ShaderNodeBsdfVelvet(RuleNodeParser):
    # inputs: Color, Sigma

    nodes = {
        "BSDF": {
            "type": pyrpr.MATERIAL_NODE_UBERV2,
            "params": {
                pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_COLOR: "inputs.Color",
                pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_WEIGHT: "inputs.Sigma",
                pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_NORMAL: "normal:inputs.Normal",
                pyrpr.UBER_MATERIAL_INPUT_REFLECTION_WEIGHT: 0.0,
                pyrpr.UBER_MATERIAL_INPUT_SHEEN_WEIGHT: 1.0,
                pyrpr.UBER_MATERIAL_INPUT_SHEEN_TINT: "inputs.Sigma",
                pyrpr.UBER_MATERIAL_INPUT_SHEEN: "inputs.Color"
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
                pyrpr.MATERIAL_INPUT_COLOR0: "inputs.Color",
                pyrpr.MATERIAL_INPUT_COLOR1: "inputs.Strength",
            }
        },
        "emission_node": {
            "type": pyrpr.MATERIAL_NODE_EMISSIVE,
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR: "nodes.emission_color"
            }
        },
        "Emission": {
            "type": pyrpr.MATERIAL_NODE_TWOSIDED,
            "params": {
                pyrpr.MATERIAL_INPUT_FRONTFACE: "nodes.emission_node",
                pyrpr.MATERIAL_INPUT_BACKFACE: "nodes.emission_node"
            }
        },

        "hybrid:Emission": {
            "type": pyrpr.MATERIAL_NODE_EMISSIVE,
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR: "nodes.emission_color"
            }
        }
    }


class ShaderNodeFresnel(RuleNodeParser):
    # inputs: IOR, Normal

    nodes = {
        "Fac": {
            "type": pyrpr.MATERIAL_NODE_FRESNEL,
            "params": {
                pyrpr.MATERIAL_INPUT_IOR: "inputs.IOR",
                pyrpr.MATERIAL_INPUT_NORMAL: "normal:inputs.Normal"
            }
        }
    }

class ShaderNodeLayerWeight(NodeParser):
    # inputs: Blend, Normal
    ''' This should do a fresnel and blend based on that.  Use Blend for ior
        This follows the cycles OSL code '''

    def export(self):
        blend = self.get_input_value('Blend')
        normal = self.get_input_normal('Normal')

        if not normal:
            normal = self.normal_node

            if not normal:
                normal = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                    pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_N
                })

        invec = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
            pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_INVEC
        })
        normal.dot3(invec)
        invec_normal = normal.dot3(invec)

        if self.socket_out.name == 'Fresnel':
            eta = (1.0 - blend).max(0.00001)
            eta2 = (invec_normal > 0.0).if_else(eta, 1.0 / eta)

            return self.create_node(pyrpr.MATERIAL_NODE_FRESNEL, {
                pyrpr.MATERIAL_INPUT_NORMAL: normal,
                pyrpr.MATERIAL_INPUT_IOR: eta2
            })

        else:
            # Facing input
            blend = blend.clamp(0.0, 0.99999)
            blend2 = (blend < 0.5).if_else(blend * 2.0, 0.5 / (1.0 - blend))

            facing = abs(invec_normal) ** blend2
            return 1.0 - facing

    def export_hybrid(self):
        return None


class ShaderNodeGamma(RuleNodeParser):
    # inputs: Color, Gamma

    nodes = {
        "Color": {
            "type": pyrpr.MATERIAL_NODE_ARITHMETIC,
            "params": {
                pyrpr.MATERIAL_INPUT_OP: pyrpr.MATERIAL_NODE_OP_POW,
                pyrpr.MATERIAL_INPUT_COLOR0: "inputs.Color",
                pyrpr.MATERIAL_INPUT_COLOR1: "inputs.Gamma",
            }
        }
    }


class ShaderNodeInvert(RuleNodeParser):
    # inputs: Fac, Color

    nodes = {
        "invert": {
            "type": "-",
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR0: 1.0,
                pyrpr.MATERIAL_INPUT_COLOR1: "inputs.Color",
            }
        },
        "Color": {
            "type": "blend",
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR0: "inputs.Color",
                pyrpr.MATERIAL_INPUT_COLOR1: "nodes.invert",
                pyrpr.MATERIAL_INPUT_WEIGHT: "inputs.Fac"
            }
        }
    }


class ShaderNodeSubsurfaceScattering(RuleNodeParser):
    # inputs: Color, Scale, Radius, Texture Blur, Normal

    nodes = {
        "radius_scale": {
            "type": "*",
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR0: "inputs.Scale",
                pyrpr.MATERIAL_INPUT_COLOR1: "inputs.Radius",
            }
        },
        "radius": {
            "type": "max",
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR0: "nodes.radius_scale",
                pyrpr.MATERIAL_INPUT_COLOR1: SSS_MIN_RADIUS
            }
        },
        "BSSRDF": {
            "type": pyrpr.MATERIAL_NODE_UBERV2,
            "params": {
                pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_WEIGHT: 1.0,
                pyrpr.UBER_MATERIAL_INPUT_REFLECTION_WEIGHT: 0.0,
                pyrpr.UBER_MATERIAL_INPUT_BACKSCATTER_WEIGHT: 1.0,
                pyrpr.UBER_MATERIAL_INPUT_BACKSCATTER_COLOR: (1.0, 1.0, 1.0, 1.0),
                pyrpr.UBER_MATERIAL_INPUT_SSS_WEIGHT: 1.0,
                pyrpr.UBER_MATERIAL_INPUT_SSS_SCATTER_COLOR: "inputs.Color",
                pyrpr.UBER_MATERIAL_INPUT_SSS_SCATTER_DISTANCE: "nodes.radius",
                pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_NORMAL: "normal:inputs.Normal"
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
        scale *= 0.125  # in RPR it is divided by 8 (or multiplied by 0.125)

        vector = self.get_input_link('Vector')
        if not vector:
            vector = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV
            })

        checker = self.create_node(pyrpr.MATERIAL_NODE_CHECKER_TEXTURE, {
            pyrpr.MATERIAL_INPUT_UV: scale * vector
        })

        if self.socket_out.name == 'Fac':
            return checker

        color1 = self.get_input_value('Color1')
        color2 = self.get_input_value('Color2')

        return checker.blend(color1, color2)

    def export_hybrid(self):
        return None


class ShaderNodeTexImage(NodeParser):
    def export(self):
        if not self.node.image:
            return self.node_item(ERROR_IMAGE_COLOR if self.socket_out.name == 'Color' else
                                  ERROR_IMAGE_COLOR[3])

        rpr_image = image.sync(self.rpr_context, self.node.image)
        if not rpr_image:
            return None

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

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, {
            pyrpr.MATERIAL_INPUT_DATA: rpr_image
        })

        vector = self.get_input_link('Vector')
        if vector:
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UV, vector)

        if self.socket_out.name == 'Alpha':
            rpr_node = rpr_node.get_channel(3)

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
        def enabled(val: [NodeItem, None]):
            if val is None:
                return False

            if isinstance(val.data, float) and math.isclose(val.data, 0.0):
                return False

            if isinstance(val.data, tuple) and \
               math.isclose(val.data[0], 0.0) and \
               math.isclose(val.data[1], 0.0) and \
               math.isclose(val.data[2], 0.0):
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
                anisotropic_rotation = 0.5 - (anisotropic_rotation % 1.0)

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

        emission = self.get_input_value('Emission')

        alpha = self.get_input_value('Alpha')
        transparency = 1.0 - alpha

        normal = self.get_input_normal('Normal')

        # TODO: use Tangent input

        # Creating uber material and set inputs to it
        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_UBERV2)

        diffuse = 1.0 - transmission

        if enabled(diffuse):
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_COLOR, base_color)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_WEIGHT, 1.0)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_ROUGHNESS, roughness)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_BACKSCATTER_WEIGHT, 0.0)

            if enabled(normal):
                rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_NORMAL, normal)
        else:
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_WEIGHT, 0.0)

        # Metallic -> Reflection (always on unless specular is set to non-physical 0.0)
        if enabled(specular):
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_WEIGHT, specular)
            # TODO: check, probably need to multiply specular by 2

            # mode 'metal' unless transmission is set and metallic is 0
            if enabled(transmission) and not enabled(metallic):
                rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_MODE,
                                   pyrpr.UBER_MATERIAL_IOR_MODE_PBR)
                rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_IOR, ior)
            else:
                rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_MODE,
                                   pyrpr.UBER_MATERIAL_IOR_MODE_METALNESS)
                rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_METALNESS, metallic)

            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_COLOR, base_color)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_ROUGHNESS, roughness)

            if enabled(normal):
                rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_NORMAL, normal)

            if enabled(anisotropic):
                rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_ANISOTROPY, anisotropic)
                rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_ANISOTROPY_ROTATION, anisotropic_rotation)

        # Clearcloat
        if enabled(clearcoat):
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_COLOR, (1.0, 1.0, 1.0, 1.0))
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_WEIGHT, clearcoat)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_ROUGHNESS, clearcoat_roughness)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_THICKNESS, 0.0)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_TRANSMISSION_COLOR, (0.0, 0.0, 0.0, 0.0))
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_MODE,
                               pyrpr.UBER_MATERIAL_IOR_MODE_PBR)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_IOR, ior)

            if enabled(clearcoat_normal):
                rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_NORMAL, clearcoat_normal)
            elif enabled(normal):
                rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_NORMAL, normal)

        # Sheen
        if enabled(sheen):
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_SHEEN_WEIGHT, sheen)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_SHEEN, base_color)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_SHEEN_TINT, sheen_tint)

        # Subsurface
        if enabled(subsurface):
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_SSS_WEIGHT, subsurface)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_SSS_SCATTER_COLOR, subsurface_color)

            # check for 0 channel value(for Cycles it means "light shall not pass" unlike "pass it all" of RPR)
            # that's why we check it with small value like 0.0001
            subsurface_radius = subsurface_radius.max(SSS_MIN_RADIUS)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_SSS_SCATTER_DISTANCE, subsurface_radius)
            # TODO: check with radius_scale = bpy.context.scene.unit_settings.scale_length * 0.1

            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_SSS_MULTISCATTER, False)
            # these also need to be set for core SSS to work.
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_BACKSCATTER_WEIGHT, subsurface)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_BACKSCATTER_COLOR, subsurface_color)

        # Emission -> Emission
        if enabled(emission):
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_EMISSION_WEIGHT, 1.0)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_EMISSION_COLOR, emission)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_EMISSION_MODE, 2)

        # Alpha -> Transparency
        if enabled(transparency):
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_TRANSPARENCY, transparency)

        # Transmission -> Refraction
        if enabled(transmission):
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFRACTION_WEIGHT, transmission)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFRACTION_COLOR, base_color)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFRACTION_ROUGHNESS, transmission_roughness)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFRACTION_IOR, ior)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFRACTION_THIN_SURFACE, False)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFRACTION_CAUSTICS, True)

            if enabled(normal):
                rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFRACTION_NORMAL, normal)

        return rpr_node


class ShaderNodeNewGeometry(RuleNodeParser):
    # outputs: Position, Normal, Tangent, True Normal, Incoming, Parametric, Backfacing, Pointiness
    # Supported outputs by RPR: Position, Normal, Incoming

    nodes = {
        "Position": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_P,
            }
        },
        "Normal": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_N,
            }
        },
        # TODO: Implement support of True Normal

        "invec": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_INVEC,
            }
        },
        "Incoming": {
            "type": "*",
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR0: -1.0,
                pyrpr.MATERIAL_INPUT_COLOR1: "nodes.invec"
            }
        },

        "hybrid:Position": None,
        "hybrid:Normal": None,
        "hybrid:incoming": None,
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

        return self.create_node(pyrpr.MATERIAL_NODE_ADD, {
            pyrpr.MATERIAL_INPUT_COLOR0: shader1,
            pyrpr.MATERIAL_INPUT_COLOR1: shader2
        })

    def export_hybrid(self):
        shader1 = self.get_input_link(0)
        if shader1:
            return shader1

        shader2 = self.get_input_link(1)
        return shader2


class ShaderNodeTexCoord(RuleNodeParser):
    # outputs: Generated, Normal, UV, Object, Camera, Window, Reflection
    # Supported outputs by RPR: Normal, UV

    nodes = {
        "Generated": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV,
            },
            "warn": "TexCoord Generated output is not supported, UV will be used"
        },
        "Normal": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_N,
            }
        },
        "UV": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV,
            }
        },
        "Object": {
            "type": pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
            "params": {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_P,
            },
            "warn": "TexCoord Object output is not supported, world coordinate will be used"
        },

        "hybrid:Generated": None,
        "hybrid:Normal": None,
        "hybrid:UV": None,
        "hybrid:Object": None,
    }


class ShaderNodeLightFalloff(NodeParser):
    ''' we don't actually do light falloff in RPR.
        So we're mainly going to pass through "strength" '''
    def export(self):
        # This shader is used in materials preview, no need to spam log.warn() here.
        # Changing to log.debug()
        log.debug("Light Falloff node is not supported, only strength will be taken",
                  self.node, self.material)

        return self.get_input_default('Strength')


class ShaderNodeMixRGB(NodeParser):

    def export(self):
        fac = self.get_input_value('Fac')
        color1 = self.get_input_value('Color1')
        color2 = self.get_input_value('Color2')

        # these mix types are copied from cycles OSL
        blend_type = self.node.blend_type
        if blend_type in ('MIX', 'COLOR'):
            rpr_node = fac.blend(color1, color2)

        elif blend_type == 'ADD':
            rpr_node = fac.blend(color1, color1 + color2)

        elif blend_type == 'MULTIPLY':
            rpr_node = fac.blend(color1, color1 * color2)

        elif blend_type == 'SUBTRACT':
            rpr_node = fac.blend(color1, color1 - color2)

        elif blend_type == 'DIVIDE':
            rpr_node = fac.blend(color1, color1 / color2)

        elif blend_type == 'DIFFERENCE':
            rpr_node = fac.blend(color1, abs(color1 - color2))

        elif blend_type == 'DARKEN':
            rpr_node = fac.blend(color1, color1.min(color2))

        elif blend_type == 'VALUE':
            rpr_node = color1

        else:
            # TODO: finish other mix types: SATURATION, HUE, LINEAR_LIGHT, SOFT_LIGHT, OVERLAY, DODGE, SCREEN, LIGHTEN, BURN
            log.warn("Ignoring unsupported Blend Type", blend_type, self.node, self.material)
            return None

        if self.node.use_clamp:
            rpr_node = rpr_node.clamp()

        return rpr_node


class ShaderNodeMath(NodeParser):
    ''' simply map the blender op types to rpr op types with included map.
        We could be more correct with "round" but I've never seen this used. '''

    def export(self):
        op = self.node.operation
        in1 = self.get_input_value(0)
        if op == 'SINE':
            res = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_SIN, in1)
        elif op == 'COSINE':
            res = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_COS, in1)
        elif op == 'TANGENT':
            res = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_TAN, in1)
        elif op == 'ARCSINE':
            res = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_ASIN, in1)
        elif op == 'ARCCOSINE':
            res = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_ACOS, in1)
        elif op == 'ARCTANGENT':
            res = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_ATAN, in1)
        elif op == 'LOGARITHM':
            res = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_LOG, in1)
        elif op == 'ABSOLUTE':
            res = abs(in1)
        elif op == 'FLOOR':
            res = in1.floor()
        elif op == 'FRACT':
            res = in1 % 1.0
        elif op == 'CEIL':
            res = in1.ceil()
        elif op == 'ROUND':
            f = in1.floor()
            res = (in1 % 1.0 < 0.5).if_else(f, f + 1.0)

        else:
            in2 = self.get_input_value(1)
            if op == 'ADD':
                res = in1 + in2
            elif op == 'SUBTRACT':
                res = in1 - in2
            elif op == 'MULTIPLY':
                res = in1 * in2
            elif op == 'DIVIDE':
                res = in1 / in2
            elif op == 'POWER':
                res = in1 ** in2
            elif op == 'MINIMUM':
                res = in1.min(in2)
            elif op == 'MAXIMUM':
                res = in1.max(in2)
            elif op == 'LESS_THAN':
                res = in1 < in2
            elif op == 'GREATER_THAN':
                res = in1 > in2
            elif op == 'MODULO':
                res = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_MOD, in1, in2)
            else:
                raise ValueError("Incorrect math operation", op)

        if self.node.use_clamp:
            res = res.clamp()

        return res


class ShaderNodeVectorMath(NodeParser):
    """ Apply vector math operations assuming Blender node was designed to work with 3-axis vectors """

    def export(self):
        op = self.node.operation
        in1 = self.get_input_value(0)

        if op == 'NORMALIZE':
            res = in1.normalize()
        else:
            in2 = self.get_input_value(1)
            if op == 'ADD':
                res = in1 + in2
            elif op == 'SUBTRACT':
                res = in1 - in2
            elif op == 'AVERAGE':
                res = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_AVERAGE, in1, in2)
            elif op == 'DOT_PRODUCT':
                res = in1.dot3(in2)
            elif op == 'CROSS_PRODUCT':
                res = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_CROSS3, in1, in2)
            else:
                raise ValueError("Incorrect operation", op)


        # Apply RGB to BW conversion for "Value" output
        if self.socket_out.name == 'Value':
            res = res.to_bw()

        return res


class ShaderNodeMixShader(NodeParser):
    # inputs = ['Fac', 1, 2]

    def export(self):
        factor = self.get_input_value('Fac')

        if isinstance(factor.data, float):
            socket_key = 1 if math.isclose(factor.data, 0.0) else \
                         2 if math.isclose(factor.data, 1.0) else \
                         None

            if socket_key:
                shader = self.get_input_link(socket_key)
                if shader:
                    return shader

                return self.create_node(pyrpr.MATERIAL_NODE_DIFFUSE)

        shader1 = self.get_input_link(1)
        shader2 = self.get_input_link(2)

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_BLEND)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_WEIGHT, factor)
        if shader1:
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_COLOR0, shader1)
        if shader2:
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_COLOR1, shader2)

        return rpr_node

    def export_hybrid(self):
        factor = self.get_input_value('Fac')

        if isinstance(factor.data, float):
            socket_key = 1 if math.isclose(factor.data, 0.0) else \
                2 if math.isclose(factor.data, 1.0) else \
                    None

            if socket_key:
                shader = self.get_input_link(socket_key)
                if shader:
                    return shader

                return self.create_node(pyrpr.MATERIAL_NODE_UBERV2, {
                    pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_WEIGHT: 1.0,
                    pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_COLOR: (1.0, 1.0, 1.0, 1.0),
                })

        return self.get_input_link(1)


class ShaderNodeNormalMap(NodeParser):
    """ blends between input vec and N based on strength """
    # inputs: Strength, Color

    def export(self):
        color = self.get_input_value('Color')
        strength = self.get_input_value('Strength')

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_NORMAL_MAP, {
            pyrpr.MATERIAL_INPUT_COLOR: color,
            pyrpr.MATERIAL_INPUT_SCALE: strength
        })

        if self.node.space != 'TANGENT':
            log.warn("Ignoring unsupported normal map space",
                     self.node.space, self.node, self.material)

        if self.node.uv_map and self.node.uv_map != "UVMap":
            log.warn("Ignoring unsupported normal map uv_map",
                     self.node.uv_map, self.node, self.material)

        return rpr_node

    def export_hybrid(self):
        return self.get_input_value('Color')


class ShaderNodeNormal(NodeParser):
    """ Has two ouputs "normal" which is just to use the normal output, and dot 
        which dot products normal output and input """
    
    def export(self):
        default = self.get_output_default(0)
        if self.socket_out.name == 'Normal':
            return default

        else:
            normal = self.get_input_value('Normal')
            return normal.dot3(default)


class ShaderNodeBump(NodeParser):
    def export(self):
        strength = self.get_input_value('Strength')
        distance = self.get_input_value('Distance')
        height = self.get_input_link('Height')
        normal = self.get_input_link('Normal')

        if height:
            distance *= height

        if self.node.invert:
            distance = -distance

        node = self.create_node(pyrpr.MATERIAL_NODE_BUMP_MAP, {
            pyrpr.MATERIAL_INPUT_COLOR: distance,
            pyrpr.MATERIAL_INPUT_SCALE: strength
        })

        if normal:
            log.warn("Normal input is not supported by ShaderNodeBump node")

        return node

    def export_hybrid(self):
        return None


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
        temperature = self.get_input_value('Temperature')

        if isinstance(temperature.data, float):
            return self.node_item(convert_kelvins_to_rgb(temperature.data))

        def rgba(t):
            return (*convert_kelvins_to_rgb(t), 1.0)

        temp_array = np.fromiter(
            (v for t in range(1000, 40000, 100)
               for v in rgba(t)),
            dtype=np.float32
        ).reshape(-1, 4)
        rpr_buffer = self.rpr_context.create_buffer(temp_array, pyrpr.BUFFER_ELEMENT_TYPE_FLOAT32)

        # convert input temperature to uv lookup in buffer
        uv = (temperature - 1000.0) / 100.0

        return self.create_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER, {
            pyrpr.MATERIAL_INPUT_DATA: rpr_buffer,
            pyrpr.MATERIAL_INPUT_UV: uv
        })

    def export_hybrid(self):
        temperature = self.get_input_scalar('Temperature')

        t = temperature.data
        if isinstance(t, tuple):
            t = t[0]

        return self.node_item(convert_kelvins_to_rgb(t))


class ShaderNodeValToRGB(NodeParser):
    """ Creates an RPR_Buffer from ramp, and samples that in node.
    """
    def export(self):
        ''' create a buffer from ramp data and sample that in nodes if connected '''
        buffer_size = 256 # hard code, this is what cycles does 

        fac = self.get_input_value('Fac')
        if isinstance(fac.data, (float, tuple)):
            data = fac.data if isinstance(fac.data, float) else (sum(fac.data[:3]) / 3)
            val = self.node.color_ramp.evaluate(data)

            if self.socket_out.name == 'Alpha':
                return self.node_item(val[3])

            return self.node_item(val)

        arr = np.fromiter(
            (v for i in range(buffer_size)
               for v in self.node.color_ramp.evaluate(i / (buffer_size - 1)))
            , dtype=np.float32
        ).reshape(-1, 4)

        # export the temperature buffer once to conserve memory
        rpr_buffer = self.rpr_context.create_buffer(arr, pyrpr.BUFFER_ELEMENT_TYPE_FLOAT32)

        uv = fac * float(buffer_size)
        buf_node = self.create_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER, {
            pyrpr.MATERIAL_INPUT_DATA: rpr_buffer,
            pyrpr.MATERIAL_INPUT_UV: uv
        })

        if self.socket_out.name == 'Alpha':
            return buf_node.get_channel(3)

        return buf_node

    def export_hybrid(self):
        fac = self.get_input_scalar('Fac')

        data = fac.data if isinstance(fac.data, float) else (sum(fac.data[:3]) / 3)
        val = self.node.color_ramp.evaluate(data)

        if self.socket_out.name == 'Alpha':
            return self.node_item(val[3])

        return self.node_item(val)


class ShaderNodeTexGradient(NodeParser):
    """ Makes a gradiant on vector input or P
    """
    def export(self):
        ''' create a buffer from ramp data and sample that in nodes if connected '''
        vec = self.get_input_link('Vector')
        if not vec:
            vec = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_P
            })

        gradiant_type = self.node.gradient_type
        x = vec.get_channel(0)
        if gradiant_type == 'LINEAR':
            val = x
        elif gradiant_type == 'QUADRATIC':
            r = x.max(0.0)
            val = r * r
        elif gradiant_type == 'EASING':
            r = x.clamp()
            t = r * r
            val = t * 3.0 -  t * r * 2.0
        elif gradiant_type == 'DIAGONAL':
            y = vec.get_channel(1)
            val = (x + y) * 0.5
        elif gradiant_type == 'RADIAL':
            y = vec.get_channel(1)
            atan2 = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_ATAN, y, x)
            val = atan2 / (2.0 * math.pi) + 0.5
        else:
            # r = max(1.0 - length, 0.0);
            length = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_LENGTH3, vec)
            r = (1.0 - length).max(0.0)
            if gradiant_type  == 'QUADRATIC_SPHERE':
                val = r * r
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
        BUFFER_SIZE = 256 # hard code, this is what cycles does

        in_col = self.get_input_value('Color')
        fac = self.get_input_value('Fac')

        # these need to be initialized for some reason
        self.node.mapping.initialize()

        def rgba(i):
            c = self.node.mapping.curves[3].evaluate(i / (BUFFER_SIZE - 1))
            return (self.node.mapping.curves[0].evaluate(c),
                    self.node.mapping.curves[1].evaluate(c),
                    self.node.mapping.curves[2].evaluate(c),
                    1.0)

        if isinstance(in_col.data, tuple):
            out_col = tuple(self.node.mapping.curves[i].evaluate(in_col.data[i]) for i in range(4))

        else:
            arr = np.fromiter(
                (v for i in range(BUFFER_SIZE)
                   for v in rgba(i)),
                dtype=np.float32
            ).reshape(-1, 4)
            rpr_buffer = self.rpr_context.create_buffer(arr, pyrpr.BUFFER_ELEMENT_TYPE_FLOAT32)

            # apply mapping to each channel
            map_r = self.create_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER, {
                pyrpr.MATERIAL_INPUT_DATA: rpr_buffer,
                pyrpr.MATERIAL_INPUT_UV: in_col.get_channel(0) * float(BUFFER_SIZE)
            })

            map_g = self.create_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER, {
                pyrpr.MATERIAL_INPUT_DATA: rpr_buffer,
                pyrpr.MATERIAL_INPUT_UV: in_col.get_channel(1) * float(BUFFER_SIZE)
            })

            map_b = self.create_node(pyrpr.MATERIAL_NODE_BUFFER_SAMPLER, {
                pyrpr.MATERIAL_INPUT_DATA: rpr_buffer,
                pyrpr.MATERIAL_INPUT_UV: in_col.get_channel(2) * float(BUFFER_SIZE)
            })

            # combine
            out_col = map_r.combine(map_g, map_b)

        return fac.blend(in_col, out_col)

    def export_hybrid(self):
        in_col = self.get_input_scalar('Color')
        fac = self.get_input_scalar('Fac')

        # these need to be initialized for some reason
        self.node.mapping.initialize()

        out_col = tuple(self.node.mapping.curves[i].evaluate(in_col.data[i]) for i in range(4))
        return fac.blend(in_col, out_col)


class ShaderNodeTexNoise(NodeParser):
    """Create RPR Noise node"""

    def export(self):
        scale = self.get_input_value('Scale')
        scale *= 0.6  # RPR Noise texture visually is about 60% of Blender Noise

        mapping = self.get_input_link('Vector')
        if not mapping:  # use default mapping if no external mapping nodes attached
            mapping = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV
            })

        return self.create_node(pyrpr.MATERIAL_NODE_NOISE2D_TEXTURE, {
            pyrpr.MATERIAL_INPUT_UV: scale * mapping
        })

    def export_hybrid(self):
        return None


class ShaderNodeMapping(NodeParser):
    """Creating mix of lookup and math nodes to adjust texture coordinates mapping in a way Cycles do"""

    def export(self):
        mapping = self.get_input_link('Vector')
        if not mapping:
            mapping = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV
            })

        # apply position
        offset = tuple(self.node.translation)
        if not (math.isclose(offset[0], 0.0) and math.isclose(offset[1], 0.0)):
            mapping = mapping - offset

        # apply rotation, Z axis only
        angle = self.node.rotation[2]  # Blender Mapping node angle is already in radians
        if angle:
            part1 = mapping.dot3((math.cos(angle), math.sin(angle), 0.0))
            part2 = mapping.dot3((-math.sin(angle), math.cos(angle), 0.0))
            mapping = part1.combine(part2, (1.0, 1.0, 1.0))

        # apply scale
        scale = tuple(self.node.scale)
        if not (math.isclose(scale[0], 1.0) and math.isclose(scale[1], 1.0) and not (math.isclose(scale[2], 1.0))):
            mapping *= scale

        if self.node.use_min:
            mapping = mapping.min(tuple(self.node.min))

        if self.node.use_max:
            mapping = mapping.max(tuple(self.node.min))

        return mapping

    def export_hybrid(self):
        return None


class ShaderNodeRGBToBW(NodeParser):
    """Convert input color or texture from RGB to grayscale colors"""

    def export(self):
        color = self.get_input_value('Color')
        return color.to_bw()


class ShaderNodeCombineXYZ(NodeParser):
    """ Combine 3 input values to vector/color (v1, v2, v3, 0.0), accept input maps """
    def export(self):
        value1 = self.get_input_value('X')
        value2 = self.get_input_value('Y')
        value3 = self.get_input_value('Z')

        return value1.combine(value2, value3)


class ShaderNodeCombineRGB(NodeParser):
    """ Combine 3 input values to vector/color (v1, v2, v3, 0.0), accept input maps """
    def export(self):
        value1 = self.get_input_value('R')
        value2 = self.get_input_value('G')
        value3 = self.get_input_value('B')

        return value1.combine(value2, value3)


class ShaderNodeSeparateRGB(NodeParser):
    """ Split input value(color) to 3 separate values by R-G-B channels """
    def export(self):
        value = self.get_input_value(0)

        if self.socket_out.name == 'R':
            return value.get_channel(0)

        if self.socket_out.name == 'G':
            return value.get_channel(1)

        return value.get_channel(2)


class ShaderNodeSeparateXYZ(NodeParser):
    """ Split input value(vector) to 3 separate values by X-Y-Z channels """
    def export(self):
        value = self.get_input_value(0)

        if self.socket_out.name == 'X':
            return value.get_channel(0)

        if self.socket_out.name == 'Y':
            return value.get_channel(1)

        return value.get_channel(2)


##
# Node Group is the material tree hidden under the ShaderNodeGroup node, with GroupInput and GroupOutput nodes.
# To parse it we have to save group node reference, walk in, parse everything inside.
# If any link goes to GroupInput socket we have to walk out via stored group node reference and find linked node.

class ShaderNodeGroup(BaseNodeParser):
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


class NodeGroupInput(BaseNodeParser):
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

        if self.node.uv_map and self.object:
            mesh = self.object.data
            primary_uv = mesh.rpr.primary_uv_layer
            if primary_uv and self.node.uv_map == primary_uv.name:
                return self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                    pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV
                })

            secondary_uv = mesh.rpr.secondary_uv_layer
            if secondary_uv and self.node.uv_map == secondary_uv.name:
                return self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                    pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV1
                })

            return None

        return self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
            pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV
        })


class ShaderNodeVolumePrincipled(NodeParser):
    def export(self):
        color = self.get_input_value('Color')
        density = self.get_input_value('Density')
        anisotropy = self.get_input_value('Anisotropy')
        absorption_color = self.get_input_value('Absorption Color')
        emission_strength = self.get_input_value('Emission Strength')
        emission_color = self.get_input_value('Emission Color')

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_VOLUME, {
            pyrpr.MATERIAL_INPUT_SCATTERING: color * density,
            pyrpr.MATERIAL_INPUT_ABSORBTION: absorption_color * density,
            pyrpr.MATERIAL_INPUT_G: anisotropy,
            pyrpr.MATERIAL_INPUT_EMISSION: emission_color * emission_strength,
            pyrpr.MATERIAL_INPUT_MULTISCATTER: True,
        })

        # getting hetero volume data
        color = self.get_input_scalar('Color')
        density = self.get_input_scalar('Density')
        if isinstance(density, tuple):
            density = density[0]

        emission = self.get_input_scalar('Emission Strength')
        if isinstance(emission, tuple):
            emission = emission[0]

        emission_color = self.get_input_scalar('Emission Color')

        # storing hetero volume data as an additional field 'data' of MatrialNode object
        rpr_node.data.data = {
            'color': color.data,
            'density': density.data,
            'emission': emission.data,
            'emission_color': emission_color.data,
        }

        return rpr_node

    def export_hybrid(self):
        return None


class ShaderNodeCombineHSV(NodeParser):
    """ Combine 3 input values to vector/color (v1, v2, v3, 0.0), accept input maps """
    def export(self):
        h = self.get_input_value('H')
        s = self.get_input_value('S')
        v = self.get_input_value('V')

        hsv = h.combine(s, v)
        return hsv.hsv_to_rgb()


class ShaderNodeSeparateHSV(NodeParser):
    """ Split input value(color) to 3 separate values by HSV channels """
    def export(self):
        value = self.get_input_value(0)
        socket = {'H': 0, 'S': 1, 'V': 2}[self.socket_out.name]

        hsv = value.rgb_to_hsv()
        return hsv.get_channel(socket)


class ShaderNodeHueSaturation(NodeParser):

    def export(self):
        # TODO: With rpr nodes such rpr node calculations slows down render very much (about 100
        #  times slower), because here we have a very complex calculations. That's why here we
        #  work only with scalar values.
        #  This has to be fixed at core side: core should provide rgb_to_hsv and hsv_to_rgb
        #  conversion.

        color = self.get_input_scalar('Color')
        fac = self.get_input_scalar('Fac')
        hue = self.get_input_scalar('Hue')
        saturation = self.get_input_scalar('Saturation')
        value = self.get_input_scalar('Value')

        hsv = color.rgb_to_hsv()
        h = (hsv.get_channel(0) + hue + 0.5) % 1.0
        s = (hsv.get_channel(1) * saturation).clamp()
        v = hsv.get_channel(2) * value

        rgb = h.combine(s, v).hsv_to_rgb()
        return fac.blend(color, rgb)


class ShaderNodeEeveeSpecular(NodeParser):
    # inputs: Base Color, Specular, Roughness,
    #    Emissive Color, Transparency, Normal,
    #    Clear Coat, Clear Coat Roughness, Clear Coat Normal,
    #    Ambient Occlusion

    def export(self):
        def enabled(val):
            if val is None:
                return False

            if isinstance(val, float) and math.isclose(val, 0.0):
                return False

            return True

        # Getting require inputs. Note: if some inputs are not needed they won't be taken
        base_color = self.get_input_value('Base Color')
        specular_color = self.get_input_value('Specular') # this is color value
        roughness = self.get_input_value('Roughness')
        emissive_color = self.get_input_value('Emissive Color')
        transparency = self.get_input_value('Transparency')
        normal = self.get_input_normal('Normal')

        clearcoat = self.get_input_value('Clear Coat')
        clearcoat_roughness = None
        clearcoat_normal = None
        if enabled(clearcoat):
            clearcoat_roughness = self.get_input_value('Clear Coat Roughness')
            clearcoat_normal = self.get_input_normal('Clear Coat Normal')

        # TODO: Enable ambient occlusion
        # ambient_occlusion = self.get_input_link('Ambient Occlusion')

        # Creating uber material and set inputs to it
        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_UBERV2)

        # Diffuse
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_COLOR, base_color)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_WEIGHT, 1.0)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_ROUGHNESS, roughness)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_BACKSCATTER_WEIGHT, 0.0)
        if enabled(normal):
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_DIFFUSE_NORMAL, normal)

        # Specular
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_COLOR, specular_color)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_WEIGHT, 1.0)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_ROUGHNESS, roughness)

        if enabled(normal):
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_REFLECTION_NORMAL, normal)

        # Emissive
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_EMISSION_COLOR, emissive_color)
        rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_EMISSION_WEIGHT, emissive_color.average_xyz())

        # Transparency
        if enabled(transparency):
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_TRANSPARENCY, transparency)

        # Clear Coat
        if enabled(clearcoat):
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_COLOR, (1.0, 1.0, 1.0, 1.0))
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_WEIGHT, clearcoat)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_ROUGHNESS, clearcoat_roughness)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_THICKNESS, 0.0)
            rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_TRANSMISSION_COLOR, (0.0, 0.0, 0.0, 0.0))

            if enabled(clearcoat_normal):
                rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_NORMAL, clearcoat_normal)
            elif enabled(normal):
                rpr_node.set_input(pyrpr.UBER_MATERIAL_INPUT_COATING_NORMAL, normal)

        return rpr_node
