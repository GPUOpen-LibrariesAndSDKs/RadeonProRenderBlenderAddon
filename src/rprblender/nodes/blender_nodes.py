#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
"""
All parser classes should:
- override NodeParser with export() method
- override RuleNodeParser with class field: node
"""

import bpy
import math
import numpy as np

import pyrpr

from rprblender.export import image, material, volume
from rprblender.utils.conversion import convert_kelvins_to_rgb
from .node_parser import BaseNodeParser, RuleNodeParser, NodeParser, MaterialError
from .node_item import NodeItem
from rprblender.engine.context_hybrid import RPRContext as RPRContextHybrid
from rprblender.engine.context_hybridpro import RPRContext as RPRContextHybridPro
from rprblender.engine.context import RPRContext2
from rprblender.utils import BLENDER_VERSION, get_prop_array_data, is_zero

from rprblender.utils import logging
log = logging.Log(tag='export.rpr_nodes')


''' TODO NODES:
    ShaderNodeAttribute
'''


ERROR_OUTPUT_COLOR = (1.0, 0.0, 1.0, 1.0)   # Corresponds Cycles error output color
ERROR_IMAGE_COLOR = (1.0, 0.0, 1.0, 1.0)    # Corresponds Cycles error image color
COLOR_GAMMA = 2.2
SSS_MIN_RADIUS = 0.0001


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
                if isinstance(self.rpr_context, (RPRContextHybrid, RPRContextHybridPro)):
                    return self.create_node(pyrpr.MATERIAL_NODE_UBERV2, {
                        pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT: 0.0,
                        pyrpr.MATERIAL_INPUT_UBER_TRANSPARENCY: (1.0, 1.0, 1.0),
                    })
                else:
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
                if isinstance(self.rpr_context, (RPRContextHybrid, RPRContextHybridPro)):
                    return self.create_node(pyrpr.MATERIAL_NODE_UBERV2, {
                        pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_COLOR: ERROR_OUTPUT_COLOR
                    })
                else:
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

        if isinstance(displacement.data, (float, tuple)):
            return self.create_node(pyrpr.MATERIAL_NODE_CONSTANT_TEXTURE, {
                pyrpr.MATERIAL_INPUT_VALUE: displacement
            })
        else:
            return displacement

    def export_hybrid(self):
        return None


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
            pyrpr.MATERIAL_INPUT_ROUGHNESS: roughness,
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
            pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT: 0.0,
            pyrpr.MATERIAL_INPUT_UBER_REFLECTION_COLOR: color,
            pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ROUGHNESS: roughness,
            pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ANISOTROPY: anisotropy,
            pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ANISOTROPY_ROTATION: rotation,
        })
        if normal:
            result.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_NORMAL, normal)

        return result


class ShaderNodeBsdfDiffuse(RuleNodeParser):
    # inputs: Color, Roughness, Normal

    nodes = {
        "BSDF": {
            "type": pyrpr.MATERIAL_NODE_DIFFUSE,
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR: "inputs.Color",
                pyrpr.MATERIAL_INPUT_ROUGHNESS: "inputs.Roughness",
                pyrpr.MATERIAL_INPUT_NORMAL: "normal:inputs.Normal"
            }
        },

        'hybrid:BSDF': {
            'type': pyrpr.MATERIAL_NODE_UBERV2,
            'params': {
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT: 1.0,
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_COLOR: 'inputs.Color',
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_ROUGHNESS: 'inputs.Roughness',
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_NORMAL: 'normal:inputs.Normal',
            }
        }
    }


class ShaderNodeBsdfGlass(NodeParser):
    # inputs: Color, Roughness, Normal, IOR

    def export(self):
        def enabled(val: [NodeItem, None]):
            if val is None:
                return False

            return not val.is_zero()

        # Getting require inputs. Note: if some inputs are not needed they won't be taken
        base_color = self.get_input_value('Color')
        roughness = self.get_input_value('Roughness')
        ior = self.get_input_value('IOR')
        normal = self.get_input_normal('Normal')

        # Creating uber material and set inputs to it
        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_UBERV2)

        # disable diffuse
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT, 0.0)
        
        # reflection
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_WEIGHT, 1.0)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_MODE,
                                   pyrpr.UBER_MATERIAL_IOR_MODE_PBR)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_IOR, ior)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_COLOR, base_color)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ROUGHNESS, roughness * roughness)

        # refraction 
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_WEIGHT, 1.0)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_COLOR, base_color)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_ROUGHNESS, roughness * roughness)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_IOR, ior)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_THIN_SURFACE, False)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_CAUSTICS, True)

        if enabled(normal):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_NORMAL, normal)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_NORMAL, normal)

        return rpr_node


class ShaderNodeBsdfGlossy(RuleNodeParser):
    # inputs: Color, Roughness, Normal

    nodes = {
        "BSDF": {
            "type": pyrpr.MATERIAL_NODE_MICROFACET,
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR: "inputs.Color",
                pyrpr.MATERIAL_INPUT_ROUGHNESS: "inputs.Roughness",
                pyrpr.MATERIAL_INPUT_NORMAL: "normal:inputs.Normal"
            }
        },
        "hybrid:BSDF": {
            "type": pyrpr.MATERIAL_NODE_UBERV2,
            "params": {
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT: 0.0,
                pyrpr.MATERIAL_INPUT_UBER_REFLECTION_WEIGHT: 1.0,
                pyrpr.MATERIAL_INPUT_UBER_REFLECTION_COLOR: "inputs.Color",
                pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ROUGHNESS: "inputs.Roughness",
                pyrpr.MATERIAL_INPUT_UBER_REFLECTION_NORMAL: "normal:inputs.Normal",
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
                pyrpr.MATERIAL_INPUT_COLOR: "inputs.Color",
                pyrpr.MATERIAL_INPUT_ROUGHNESS: "inputs.Roughness",
                pyrpr.MATERIAL_INPUT_NORMAL: "normal:inputs.Normal",
                pyrpr.MATERIAL_INPUT_IOR: "inputs.IOR"
            }
        },
        "hybrid:BSDF": {
            "type": pyrpr.MATERIAL_NODE_UBERV2,
            "params": {
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT: 0.0,
                pyrpr.MATERIAL_INPUT_UBER_REFRACTION_WEIGHT: 1.0,
                pyrpr.MATERIAL_INPUT_UBER_REFRACTION_COLOR: "inputs.Color",
                pyrpr.MATERIAL_INPUT_UBER_REFRACTION_ROUGHNESS: "inputs.Roughness",
                pyrpr.MATERIAL_INPUT_UBER_REFRACTION_NORMAL: "normal:inputs.Normal",
                pyrpr.MATERIAL_INPUT_UBER_REFRACTION_IOR: "inputs.IOR"
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
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT: 1.0,
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_COLOR: "inputs.Color",
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_NORMAL: "normal:inputs.Normal",
                pyrpr.MATERIAL_INPUT_UBER_REFRACTION_WEIGHT: 1.0,
                pyrpr.MATERIAL_INPUT_UBER_REFRACTION_COLOR: "inputs.Color",
                pyrpr.MATERIAL_INPUT_UBER_REFRACTION_NORMAL: "normal:inputs.Normal",
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
            pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT: 1.0,
            pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_ROUGHNESS: 0.0,
            pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_COLOR: color,
            pyrpr.MATERIAL_INPUT_UBER_TRANSPARENCY: color.average_xyz(),
        })


class ShaderNodeBsdfVelvet(RuleNodeParser):
    # inputs: Color, Sigma

    nodes = {
        "ONE_MINUS_SIGMA": {
            "type": "-",
            "params": {
                pyrpr.MATERIAL_INPUT_COLOR0: 1.0,
                pyrpr.MATERIAL_INPUT_COLOR1: "inputs.Sigma",
            }
        },

        "BSDF": {
            "type": pyrpr.MATERIAL_NODE_UBERV2,
            "params": {
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_COLOR: "inputs.Color",
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT: "nodes.ONE_MINUS_SIGMA",
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_NORMAL: "normal:inputs.Normal",
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_ROUGHNESS: 1.0,
                pyrpr.MATERIAL_INPUT_UBER_REFLECTION_WEIGHT: 0.0,
                pyrpr.MATERIAL_INPUT_UBER_SHEEN_WEIGHT: "inputs.Sigma",
                pyrpr.MATERIAL_INPUT_UBER_SHEEN_TINT: 1.0,
                pyrpr.MATERIAL_INPUT_UBER_SHEEN: "inputs.Color"
            }
        }
    }


class ShaderNodeEmission(RuleNodeParser):
    # inputs: Color, Strength

    nodes = {
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
    """ This should do a fresnel and blend based on that.  Use Blend for ior
        This follows the cycles OSL code """

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
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT: 1.0,
                pyrpr.MATERIAL_INPUT_UBER_REFLECTION_WEIGHT: 0.0,
                pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_WEIGHT: 1.0,
                pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_COLOR: (1.0, 1.0, 1.0, 1.0),
                pyrpr.MATERIAL_INPUT_UBER_SSS_WEIGHT: 1.0,
                pyrpr.MATERIAL_INPUT_UBER_SSS_SCATTER_COLOR: "inputs.Color",
                pyrpr.MATERIAL_INPUT_UBER_SSS_SCATTER_DISTANCE: "nodes.radius",
                pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_NORMAL: "normal:inputs.Normal"
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
        wrap_mapping = {
            'REPEAT': pyrpr.IMAGE_WRAP_TYPE_REPEAT,
            'EXTEND': pyrpr.IMAGE_WRAP_TYPE_CLAMP_TO_EDGE,
            'CLIP': pyrpr.IMAGE_WRAP_TYPE_CLAMP_ZERO,
        }

        return self._export_image_node(wrap_mapping)

    def export_hybrid(self):
        # Hybrid has separate list of supported wrap types
        wrap_mapping_hybrid = {
            'REPEAT': pyrpr.IMAGE_WRAP_TYPE_REPEAT,
            'EXTEND': pyrpr.IMAGE_WRAP_TYPE_CLAMP_TO_EDGE,
        }

        return self._export_image_node(wrap_mapping_hybrid)

    def _export_image_node(self, wrap_mapping):
        """ Export image node as RPR node using supported wrapping types """
        if not self.node.image:
            return self.node_item(ERROR_IMAGE_COLOR if self.socket_out.name == 'Color' else
                                  ERROR_IMAGE_COLOR[3])

        frame_current = self.node.image_user.frame_current

        # generating frame_current if use_auto_refresh is off, due to blender provides incorrect value in some cases
        if not self.node.image_user.use_auto_refresh:
            frame_duration = self.node.image_user.frame_duration
            frame_start = self.node.image_user.frame_start
            frame_offset = self.node.image_user.frame_offset
            frame_finish = frame_offset + frame_duration
            frame_current = self.rpr_context.blender_data['depsgraph'].scene.frame_current
            if self.node.image_user.use_cyclic:
                frame_current = (frame_current - frame_start) % frame_duration + frame_offset + 1
            else:
                frame_current = min(frame_current - frame_start + frame_offset + 1, frame_finish)

        rpr_image = image.sync(self.rpr_context, self.node.image, frame_number=frame_current)
        if not rpr_image:
            return None

        if self.node.extension in wrap_mapping:
            rpr_image.set_wrap(wrap_mapping[self.node.extension])
        else:
            log.warn(f"Unsupported image wrap type {self.node.extension}")
            rpr_image.set_wrap(pyrpr.IMAGE_WRAP_TYPE_REPEAT)

        if self.node.interpolation != 'Linear':
            log.warn("Ignoring unsupported texture interpolation", self.node.interpolation, self.node, self.material)

        if self.node.projection == 'BOX':
            p = self.get_input_link('Vector')
            if not p:
                # this is a bit undefined.
                p = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                    pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_P_LOCAL
                })

            normal = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_N
            })

            x = p.get_channel(0)
            y = p.get_channel(1)
            z = p.get_channel(2)

            uv_xy = (normal.get_channel(2) < 0.0).if_else(y, -y).combine4(x, 0.0, 0.0)
            uv_yz = (normal.get_channel(0) < 0.0).if_else(-y, y).combine4(z, 0.0, 0.0)
            uv_xz = (normal.get_channel(1) < 0.0).if_else(x, -x).combine4(z, 0.0, 0.0)

            # lookup texture three times for each uv combo
            tex_xy = self.create_node(pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, {
                pyrpr.MATERIAL_INPUT_DATA: rpr_image,
                pyrpr.MATERIAL_INPUT_UV: uv_xy
            })
            tex_yz = self.create_node(pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, {
                pyrpr.MATERIAL_INPUT_DATA: rpr_image,
                pyrpr.MATERIAL_INPUT_UV: uv_yz
            })
            tex_xz = self.create_node(pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, {
                pyrpr.MATERIAL_INPUT_DATA: rpr_image,
                pyrpr.MATERIAL_INPUT_UV: uv_xz
            })

            # calculate blend factor
            blend = 1.0 / (self.node.projection_blend
                           if not math.isclose(self.node.projection_blend, 0.0) else 999.9)

            weights = abs(normal) * blend
            weights = weights / (weights.get_channel(0) + weights.get_channel(1) +
                                 weights.get_channel(2))

            # blend three images based on normal dir
            rpr_node = tex_yz * weights.get_channel(0) + \
                       tex_xz * weights.get_channel(1) + \
                       tex_xy * weights.get_channel(2)

        else:
            rpr_node = self.create_node(pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, {
                pyrpr.MATERIAL_INPUT_DATA: rpr_image
            })

            vector = self.get_input_link('Vector')
            if vector:
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UV, vector)


            if self.node.projection != 'FLAT':
                log.warn("Ignoring unsupported texture projection", self.node.projection, self.node, self.material)

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
        # Getting require inputs. Note: if some inputs are not needed they won't be taken
        base_color = self.get_input_value('Base Color')

        subsurface = self.get_input_value('Subsurface')
        subsurface_radius = None
        subsurface_color = None
        if enabled(subsurface):
            subsurface_radius = self.get_input_value('Subsurface Radius')
            subsurface_color = self.get_input_value('Subsurface Color')

        metallic = self.get_input_value('Metallic')
        specular = self.get_input_value('Specular')
        roughness = self.get_input_value('Roughness')

        anisotropic = None
        anisotropic_rotation = None
        if enabled(metallic):
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
        emission_strength = 1.0

        # 'Emission Strength' in ShaderNodeBsdfPrincipled is supported from blender 2.91
        if enabled(emission) and BLENDER_VERSION >= '2.91':
            emission_strength = self.get_input_value('Emission Strength')

        alpha = self.get_input_value('Alpha')
        transparency = 1.0 - alpha

        normal = self.get_input_normal('Normal')

        # TODO: use Tangent input

        # Creating uber material and set inputs to it
        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_UBERV2)

        # looks like diffuse should be always enabled, regarding cycles
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_COLOR, base_color)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT, 1.0)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_ROUGHNESS, roughness)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_WEIGHT, 0.0)

        if enabled(normal):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_NORMAL, normal)

        # setting reflection weight as max of specular and metallic weights
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_WEIGHT, specular.max(metallic))
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ROUGHNESS, roughness)
        #rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_IOR, ior)

        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_MODE,
                            pyrpr.UBER_MATERIAL_IOR_MODE_METALNESS)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_METALNESS, metallic)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_COLOR, base_color)

        if enabled(normal):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_NORMAL, normal)

        if enabled(anisotropic):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ANISOTROPY, anisotropic)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ANISOTROPY_ROTATION,
                                anisotropic_rotation)
        # Clearcloat
        if enabled(clearcoat):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_COLOR, (1.0, 1.0, 1.0, 1.0))
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_WEIGHT, clearcoat)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_ROUGHNESS, clearcoat_roughness)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_THICKNESS, 0.0)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_TRANSMISSION_COLOR, (0.0, 0.0, 0.0, 0.0))
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_MODE,
                               pyrpr.UBER_MATERIAL_IOR_MODE_PBR)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_IOR, ior)

            if enabled(clearcoat_normal):
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_NORMAL, clearcoat_normal)
            elif enabled(normal):
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_NORMAL, normal)

        # Sheen
        if enabled(sheen):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SHEEN_WEIGHT, sheen)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SHEEN, base_color)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SHEEN_TINT, sheen_tint)

        # Subsurface
        if enabled(subsurface):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SSS_WEIGHT, subsurface)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SSS_SCATTER_COLOR, subsurface_color)

            # check for 0 channel value(for Cycles it means "light shall not pass"
            # unlike "pass it all" of RPR) that's why we check it with small value like 0.0001
            subsurface_radius = subsurface_radius.max(SSS_MIN_RADIUS)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SSS_SCATTER_DISTANCE, subsurface_radius)
            # TODO: check with radius_scale = bpy.context.scene.unit_settings.scale_length * 0.1

            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_SSS_MULTISCATTER, False)
            # these also need to be set for core SSS to work.
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_WEIGHT, subsurface)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_COLOR, subsurface_color)

        # Emission -> Emission
        if enabled(emission):
            # more related formula for emission weight:
            emission *= emission_strength
            emission_weight = emission.average_xyz().min(1.0) * 0.5 + 0.5

            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_EMISSION_WEIGHT, emission_weight)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_EMISSION_COLOR, emission)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_EMISSION_MODE,
                               pyrpr.UBER_MATERIAL_EMISSION_MODE_DOUBLESIDED)  # double sided

        # Alpha -> Transparency
        if enabled(transparency):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_TRANSPARENCY, transparency)

        # Transmission -> Refraction
        if enabled(transmission):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_WEIGHT, transmission)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_COLOR, base_color)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_ROUGHNESS, transmission_roughness)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_IOR, ior)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_THIN_SURFACE, False)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_CAUSTICS, True)

            if enabled(normal):
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFRACTION_NORMAL, normal)

        return rpr_node


class ShaderNodeBsdfHair(NodeParser):
    """ Cycles Hair BSDF has two modes, transmission and reflection.
        Use "WARD" for reflection and transparent for transmission """

    def export(self):
        # Getting require inputs. Note: if some inputs are not needed they won't be taken
        component = self.node.component
        base_color = self.get_input_value('Color')

        rotation_angle = self.get_input_value('Offset')
        roughness_u = self.get_input_value('RoughnessU').clamp(0.001, 1.0)
        roughness_v = self.get_input_value('RoughnessV').clamp(0.001, 1.0)

        # TODO: use Tangent input

        # Treat reflection as a WARD shader
        if component == 'Reflection':
            rpr_node = self._create_ward_node(base_color, roughness_u, roughness_v, rotation_angle)
        else:
            roughness = (roughness_u + roughness_v) * 0.5
            rpr_node = self._create_transmission_node(base_color, roughness)

        return rpr_node

    def export_rpr2(self):
        component = self.node.component
        base_color = self.get_input_value('Color')

        rotation_angle = self.get_input_value('Offset')
        roughness_u = self.get_input_value('RoughnessU').clamp(0.001, 1.0)
        roughness_v = self.get_input_value('RoughnessV').clamp(0.001, 1.0)

        # Treat reflection as and Uber shader with anisotropic reflection
        if component == 'Reflection':
            rotation_angle = 0.5 - rotation_angle % math.pi  # fit angle to the range [-0.5..+0.5]

            rpr_node = self._create_aniso_reflection_node(base_color, roughness_u, roughness_v,
                                                          rotation_angle)
        else:
            roughness = (roughness_u + roughness_v) * 0.5
            rpr_node = self._create_transmission_node(base_color, roughness)

        return rpr_node

    def export_hybrid(self):
        # we'll just use roughness_u and uber for bsdf 
        component = self.node.component
        color = self.get_input_value('Color')

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_UBERV2)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT, 0.0)

        if component == 'Reflection':
            roughness_u = self.get_input_value('RoughnessU').clamp(0.001, 1.0)
            roughness_v = self.get_input_value('RoughnessV').clamp(0.001, 1.0)
            roughness = (roughness_u + roughness_v) * 0.5

            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_WEIGHT, 1.0)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_COLOR, color)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ROUGHNESS, roughness)
        else:
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_TRANSPARENCY, color)

        return rpr_node

    def _create_ward_node(self, base_color, roughness_u, roughness_v, rotation_angle):
        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_WARD)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_ROUGHNESS_X, roughness_u)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_ROUGHNESS_Y, roughness_v)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_ROTATION, rotation_angle)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_COLOR, base_color)
        return rpr_node

    def _create_aniso_reflection_node(self, base_color, roughness_u, roughness_v, rotation_angle):
        rotation_angle = 0.5 - rotation_angle % math.pi  # fit angle to the range [-0.5..+0.5]

        rough_max = roughness_v.max(roughness_u)
        rough_min = roughness_v.min(roughness_u)

        anisotropy = 0
        if not roughness_u.data == roughness_v.data:
            anisotropy = (rough_max - rough_min).clamp(0.001, 1.0)  # limit anisotropy amount

        # a rough approximation of reflection roughness
        rough_med = (roughness_u + roughness_v) * 0.5
        rough_aniso = (rough_min + rough_med) * 0.5

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_UBERV2)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT, 0.0)

        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_WEIGHT, 1.0)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_COLOR, base_color)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ROUGHNESS, rough_aniso)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ANISOTROPY, anisotropy)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ANISOTROPY_ROTATION, rotation_angle)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_MODE,
                           pyrpr.UBER_MATERIAL_IOR_MODE_METALNESS)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_METALNESS, 1.0)

        return rpr_node

    def _create_transmission_node(self, base_color, roughness):
        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_UBERV2, {
            pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT: 0.0,
            pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_COLOR: base_color,
            pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_ROUGHNESS: roughness,
            pyrpr.MATERIAL_INPUT_UBER_REFLECTION_WEIGHT: 0.0,
            pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_WEIGHT: 1.0,
            pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_COLOR: base_color,
        })
        return rpr_node


class ShaderNodeBsdfHairPrincipled(NodeParser):
    """ Partial support for Cycles Principled Hair BSDF shader node """

    def export(self) -> [NodeItem, None]:
        parametrization = self.node.parametrization

        roughness = self.get_input_value('Roughness').clamp(0.001, 1.0)
        roughness_radial = self.get_input_value('Radial Roughness').clamp(0.001, 1.0)
        coat = self.get_input_scalar('Coat')
        ior = self.get_input_scalar('IOR')
        weight = 0.0
        melanin = 0.0

        if parametrization == 'ABSORPTION':
            absorption_color = self.get_input_value('Absorption Coefficient')
            color = (1.0 - absorption_color).min(1.0)
        elif parametrization == 'MELANIN':
            melanin = self.get_input_scalar('Melanin')
            melanin_redness = self.get_input_scalar('Melanin Redness')
            absorption_color = self._calculate_absorption_from_melanin(melanin, melanin_redness).min(1.0)
            color = 1.0 - absorption_color
        else:  # 'COLOR'
            color = self.get_input_value('Color')
            weight = 1.0

        node = self._create_absorption_node(color, weight, melanin, roughness, roughness_radial, coat, ior)
        return node

    def _calculate_absorption_from_melanin(self, melanin, melanin_redness):
        """ Use the Cycles way from bsdf_principled_hair_sigma_from_concentration """
        # see the node Blender Manual https://docs.blender.org/manual/en/latest/render/shader_nodes/shader/hair_principled.html
        eumelanin = melanin * (1.0 - melanin_redness)
        pheomelanin = melanin * melanin_redness
        result = eumelanin * (0.506, 0.841, 1.653) + pheomelanin * (0.343, 0.733, 1.924)
        return result

    def _create_absorption_node(self, color, weight, melanin, roughness, roughness_radial, coat, ior):

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_UBERV2)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_COLOR, color)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT, weight)

        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_WEIGHT, 1.0 - melanin)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_COLOR, color)

        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_WEIGHT, 1.0 - roughness)  # length roughness increases gloss
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_COLOR, (1.0, 1.0, 1.0, 1.0))
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ROUGHNESS, roughness_radial)  # decreases gloss, increases overall lightness
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_IOR, ior)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_MODE,
                           pyrpr.UBER_MATERIAL_IOR_MODE_PBR)

        if coat is not None or (isinstance(coat, float) and math.isclose(coat, 0.0)):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_WEIGHT, coat)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_COLOR, color)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_ROUGHNESS, 0)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_IOR, ior)

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


class ShaderNodeObjectInfo(NodeParser):

    def export(self):
        if self.socket_out.name == 'Location':
            if self.object:
                return self.node_item(tuple(self.object.location))
            else:
                return self.node_item((0.0, 0.0, 0.0, 0.0))
        elif self.socket_out.name == 'Color':
            if self.object:
                return self.node_item(tuple(self.object.color))
            else:
                return self.node_item((1.0, 1.0, 1.0, 1.0))
        elif self.socket_out.name == 'Object Index':
            if self.object:
                return self.node_item(float(self.object.pass_index))
            else:
                return self.node_item(0.0)
        elif self.socket_out.name == 'Material Index':
            return self.node_item(float(self.material.pass_index))
        elif self.socket_out.name == 'Random':
            return self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP,
                                    {pyrpr.MATERIAL_INPUT_VALUE:
                                     pyrpr.MATERIAL_NODE_LOOKUP_SHAPE_RANDOM_COLOR})

    def export_hybrid(self):
        if self.socket_out.name == 'Random':
            log.warn(f"Unsupported random object info in Hybrid modes")
            return self.node_item(float(self.object.pass_index))
        else:
            return self.export()


class ShaderNodeTexCoord(RuleNodeParser):
    # outputs: Generated, Normal, UV, Object, Camera, Window, Reflection
    # Supported outputs by RPR: Normal, UV

    def export(self):
        tex_coord_type = self.socket_out.name

        if tex_coord_type == 'Generated':
            data = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_P_LOCAL,
            })
            if self.object:
                # normalize over object bounding box
                # get min and max of bounding box
                min_bounds = tuple(min(p[i] for p in self.object.bound_box) for i in range(3))
                max_bounds = tuple(max(p[i] for p in self.object.bound_box) for i in range(3))

                size = self.node_item((max_bounds[0] - min_bounds[0],
                                       max_bounds[1] - min_bounds[1],
                                       max_bounds[2] - min_bounds[2]))
                min_bounds = self.node_item(min_bounds)

                data = (data - min_bounds) / size

        elif tex_coord_type == 'Normal':
            data = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_N,
            })
        elif tex_coord_type == 'UV':
            data = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV,
            })
        elif tex_coord_type == 'Object':
            data = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_P_LOCAL,
            })
        else:
            log.warn("Ignoring unsupported UV lookup", tex_coord_type, self.node, self.material, 
                     "UV will be used")
            data = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV,
            })

        return data


class ShaderNodeLightFalloff(NodeParser):
    """ we don't actually do light falloff in RPR.
        So we're mainly going to pass through "strength" """
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

        elif blend_type == 'LIGHTEN':
            rpr_node = fac.blend(color1, color1.max(color2))

        elif blend_type == 'VALUE':
            rpr_node = color1

        elif blend_type == 'OVERLAY':
            test_val = color1 < 0.5

            rpr_node = fac.blend(color1, test_val.if_else(2.0 * color1 * color2,
                (1.0 - (1.0 - color1) * (1.0 - color2))))

        elif blend_type == 'SCREEN':
            tm = 1.0 - fac
            rpr_node = 1.0 - (tm + fac * (1.0 - color2)) * (1.0 - color1)

        elif blend_type == 'SOFT_LIGHT':
            tm = 1.0 - fac
            scr = 1.0 - (1.0 - color2) * (1.0 - color1)
            rpr_node = tm * color1 + fac * ((1.0 - color1) * color2 * color1 + color1 * scr)

        elif blend_type == 'LINEAR_LIGHT':
            test_val = color2 > 0.5
            rpr_node = test_val.if_else(color1 + fac * (2.0 * (color2 - 0.5)),
                                        color1 + fac * (2.0 * color2 - 1.0))

        else:
            # TODO: finish other mix types: SATURATION, HUE, SCREEN, BURN
            log.warn("Ignoring unsupported Blend Type", blend_type, self.node, self.material, 
                     "mix will be used")
            rpr_node = fac.blend(color1, color2)

        if self.node.use_clamp:
            rpr_node = rpr_node.clamp()

        return rpr_node

    def export_hybrid(self) -> [NodeItem, None]:
        blend_type = self.node.blend_type

        if blend_type in ('OVERLAY', 'LINEAR_LIGHT', ):
            log.warn(f"Ignoring unsupported MixRGB type", blend_type, self.node, self.material)
            return None

        # other operations are supported by Hybrid
        return self.export()


class ShaderNodeMath(NodeParser):
    """ simply map the blender op types to rpr op types with included map.
        We could be more correct with "round" but I've never seen this used. """

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
                in3 = self.get_input_value(2)
                if op == 'MULTIPLY_ADD':
                    res = in1 * in2 + in3
                elif op == 'COMPARE':
                    # Descriptions from Cycles: Outputs 1.0 if the difference
                    # between the two input values is less than or equal to Epsilon.
                    res = abs(in1 - in2) <= in3
                elif op == 'SMOOTH_MIN':
                    # Descriptions from Cycles: https://en.wikipedia.org/wiki/Smooth_maximum
                    f1 = math.e ** (in1 * in3)
                    f2 = math.e ** (in2 * in3)
                    res = (in1 * f2 + in2 * f1) / (f1 + f2)
                elif op == 'SMOOTH_MAX':
                    # Descriptions from Cycles: https://en.wikipedia.org/wiki/Smooth_maximum
                    f1 = math.e ** (in1 * in3)
                    f2 = math.e ** (in2 * in3)
                    res = (in1 * f1 + in2 * f2) / (f1 + f2)

                else:
                    res = in1
                    log.warn("Unsupported math operation", op)

        if self.node.use_clamp:
            res = res.clamp()

        return res

    def export_hybrid(self) -> [NodeItem, None]:
        op = self.node.operation

        if op in ('LOGARITHM', 'CEIL', 'LESS_THAN', 'GREATER_THAN'):
            log.warn(f"Ignoring unsupported Math operation", op, self.node, self.material)
            return None

        # other operations are supported by Hybrid
        return self.export()


class ShaderNodeVectorMath(NodeParser):
    """ Apply vector math operations assuming Blender node was designed to work with 3-axis vectors """

    def export(self):
        op = self.node.operation
        in1 = self.get_input_value(0)

        if op == 'NORMALIZE':
            res = in1.normalize()
        elif op == 'FLOOR':
            res = in1.floor()
        elif op == 'CEIL':
            res = in1.ceil()
        elif op == 'LENGTH':
            res = in1.length()
        elif op == 'ABSOLUTE':
            res = abs(in1)
        elif op == 'SINE':
            res = in1.sin()
        elif op == 'COSINE':
            res = in1.cos()
        elif op == 'TANGENT':
            res = in1.tan()
        elif op == 'FRACTION':
            res = in1 - in1.floor()
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
            elif op == 'AVERAGE':
                res = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_AVERAGE, in1, in2)
            elif op == 'DOT_PRODUCT':
                res = in1.dot3(in2)
            elif op == 'CROSS_PRODUCT':
                res = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_CROSS3, in1, in2)
            elif op == 'MINIMUM':
                res = min(in1, in2)
            elif op == 'MAXIMUM':
                res = max(in1, in2)
            elif op == 'MODULO':
                res = in1 % in2
            elif op == 'PROJECT':
                len_sq = in2.dot3(in2)
                res = (len_sq != 0.0).if_else(in1.dot3(in2) / len_sq, 0.0)
            elif op == 'REFLECT':
                in2_norm = in2.normalize()
                res = in1 - in2_norm.dot3(in1) * 2.0 * in2_norm
            elif op == 'DISTANCE':
                diff = in1 - in2
                res = diff.length()
            elif op == 'SNAP':
                res = (in1 / in2).floor() * in2
            elif op == 'SCALE':
                # input 2 here is a scalar
                res = in1 * in2
            else:  # 3-inputs operations
                in3 = self.get_input_value(2)

                if op == 'WRAP':
                    # adapted from Blender util_math.h wrapf method
                    val_range = in2 - in3
                    if val_range != 0.0:
                        res = in1 - val_range * ((in1 - in3) / val_range).floor()
                    else:
                        res = in3
                else:
                    raise ValueError("Incorrect operation", op)

        # Apply RGB to BW conversion for "Value" output
        if self.socket_out.name == 'Value':
            res = res.to_bw()

        return res

    def export_hybrid(self) -> [NodeItem, None]:
        op = self.node.operation

        if op in ('PROJECT', ):
            log.warn(f"Ignoring unsupported Vector Math operation", op, self.node, self.material)
            return None

        # other operations are supported by Hybrid
        return self.export()


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
                    pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT: 1.0,
                    pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_COLOR: (1.0, 1.0, 1.0, 1.0),
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
    """ Has two outputs "normal" which is just to use the normal output, and dot
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

        if not height or strength.is_zero():
            # nothing hooked up to height?  Just use normal
            return self.get_input_normal('Normal')

        # RPR "ShaderNodeBump" strength visually needs to be about 10 times greater to match Cycles result.
        strength *= 10.0

        # mix normal with bump over normal via strength factor
        # strength is named "factor" in other nodes

        if self.node.invert:
            distance = -distance

        bump_node = self.create_node(pyrpr.MATERIAL_NODE_BUMP_MAP, {
            pyrpr.MATERIAL_INPUT_COLOR: height * distance,
            pyrpr.MATERIAL_INPUT_SCALE: strength
        })

        # use surface normal if not hooked up
        if normal is None:
            normal_node = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_N
            })
        else:
            # RPR normal map seems stronger than cycles here.  But this is expected?
            normal_node = self.create_node(pyrpr.MATERIAL_NODE_NORMAL_MAP, {
                pyrpr.MATERIAL_INPUT_COLOR: normal,
            })

        return strength.blend(normal_node, bump_node + normal_node)

    def export_hybridpro(self):
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
        """ create a buffer from ramp data and sample that in nodes if connected """
        buffer_size = 256  # hard code, this is what cycles does

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


class ShaderNodeMapRange(NodeParser):
    """ Just a simple range conversion
    """
    def export(self):
        # TODO add suport for more than just linear mapping

        ''' Get an input value like this.  
            This creates rpr "shader nodes" behind the scenes.
        '''
        from_min = self.get_input_value('From Min')  
        from_max = self.get_input_value('From Max')
        to_min = self.get_input_value('To Min')
        to_max = self.get_input_value('To Max')
        
        ''' Doing math like this is actually compiled into a 
            shader that is executed at runtime. '''
        from_range = from_max - from_min  
        to_range = to_max - to_min
        value = self.get_input_value('Value')
        if self.node.clamp:  # you can access node values like this
            value = value.clamp(from_min, from_max)
        point_in_from_range = value - from_min
        result_shader_node = from_min + point_in_from_range * (to_range / from_range)

        return result_shader_node


class ShaderNodeTexGradient(NodeParser):
    """ Makes a gradiant on vector input or P
    """
    def export(self):
        """ create a buffer from ramp data and sample that in nodes if connected """
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
            val = t * 3.0 - t * r * 2.0
        elif gradiant_type == 'DIAGONAL':
            y = vec.get_channel(1)
            val = (x + y) * 0.5
        elif gradiant_type == 'RADIAL':
            y = vec.get_channel(1)
            atan2 = self.create_arithmetic(pyrpr.MATERIAL_NODE_OP_ATAN, y, x)
            val = atan2 / (2.0 * math.pi) + 0.5
        else:
            # r = max(1.0 - length, 0.0);
            length = vec.length()
            r = (1.0 - length).max(0.0)
            if gradiant_type == 'QUADRATIC_SPHERE':
                val = r * r
            else:  # 'SPHERICAL'
                val = r

        return val


class ShaderNodeRGBCurve(NodeParser):
    """ Similar to color ramp, except read each channel and apply mapping
        There are two inputs here, color and Fac.  What cycles does is remap color with the mapping
        and mix between in color and remapped one with fac.
    """
    @staticmethod
    def eval_curve(mapping: bpy.types.CurveMapping, curve_index: int, value: float) -> float:
        """ Evaluate 'value' on 'mapping' RGB Curve 'curve_index', clip to limits if needed """
        if mapping.use_clip:
            value = min(max(value, mapping.clip_min_x), mapping.clip_max_x)

        if BLENDER_VERSION >= '2.82':  # CurveMapping and CurveMap were changed in Blender release 2.82
            res = mapping.evaluate(mapping.curves[curve_index], value)
        else:
            res = mapping.curves[curve_index].evaluate(value)

        if mapping.use_clip:
            res = min(max(res, mapping.clip_min_y), mapping.clip_max_y)

        return res

    def export(self):
        """ create a buffer from ramp data and sample it in nodes if connected """
        def rgba(i):
            c = self.eval_curve(mapping, 3, i / (BUFFER_SIZE - 1))
            return (self.eval_curve(mapping, 0, c),
                    self.eval_curve(mapping, 1, c),
                    self.eval_curve(mapping, 2, c),
                    1.0)

        BUFFER_SIZE = 256  # hard code, this is what cycles does

        in_col = self.get_input_value('Color')
        fac = self.get_input_value('Fac')
        mapping = self.node.mapping

        # these need to be initialized for some reason
        mapping.initialize()

        if isinstance(in_col.data, tuple):
            out_col = tuple(
                self.eval_curve(mapping, i,
                                self.eval_curve(mapping, 3, in_col.data[i]))
                for i in range(3)
            ) + (in_col.data[3],)

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
        """ Convert color using channel curves """
        in_col = self.get_input_scalar('Color')
        fac = self.get_input_scalar('Fac')
        mapping = self.node.mapping

        # these need to be initialized for some reason
        mapping.initialize()

        out_col = tuple(
            self.eval_curve(mapping, i,
                            self.eval_curve(mapping, 3, in_col.get_channel(i).data))
            for i in range(3)
        ) + (in_col.get_channel(3).data,)

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


class ShaderNodeTexVoronoi(NodeParser):
    """Create RPR Voronoi node"""

    def export_rpr2(self):
        if self.node.voronoi_dimensions in ('1D', '4D'):
            log.warn("Unsupported dimension type", self.node.voronoi_dimensions, self.node,
                     self.material)
            return None

        if self.node.feature != 'F1':
            log.warn("Unsupported feature type", self.node.feature, self.node, self.material)
            return None

        if self.node.distance != 'EUCLIDEAN':
            log.warn("Unsupported distance type", self.node.distance, self.node, self.material)
            return None

        scale = self.get_input_value('Scale')
        scale *= 3.5 # RPR Voronoi texture visually is about 350% of Blender Voronoi
        randomness = self.get_input_value('Randomness')
        dimensions = 2 if self.node.voronoi_dimensions == '2D' else 3

        mapping = self.get_input_link('Vector')
        if not mapping:  # use default mapping if no external mapping nodes attached
            mapping = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV
            })

        out_type = {
            'Distance': pyrpr.VORONOI_OUT_TYPE_DISTANCE,
            'Color': pyrpr.VORONOI_OUT_TYPE_COLOR,
            'Position': pyrpr.VORONOI_OUT_TYPE_POSITION
        }[self.socket_out.name]

        voronoi = self.create_node(pyrpr.MATERIAL_NODE_VORONOI_TEXTURE, {
            pyrpr.MATERIAL_INPUT_UV: mapping,
            pyrpr.MATERIAL_INPUT_SCALE: scale,
            pyrpr.MATERIAL_INPUT_RANDOMNESS: randomness,
            pyrpr.MATERIAL_INPUT_DIMENSION: dimensions,
            pyrpr.MATERIAL_INPUT_OUTTYPE: out_type,
        })

        return voronoi

    def export(self):
        return None

    def export_hybrid(self):
        return None


class ShaderNodeMapping(NodeParser):
    """Creating mix of lookup and math nodes to adjust texture coordinates mapping in a way Cycles do"""

    def export(self):
        """ Export node by version as it was changed in 2.81 """
        if BLENDER_VERSION == '2.80':  # running on Blender 2.80
            return self.export_280()

        return self.export_281()

    def rotation(self, mapping, transpose=False):
        """ returns a vector transformed by rotation """
        # Apply rotation to transpose we flip matrix
        rotation = - self.get_input_default('Rotation')  # must be flipped to match cycles
        sin_x, sin_y, sin_z = map(math.sin, rotation.data)
        cos_x, cos_y, cos_z = map(math.cos, rotation.data)

        if transpose:
            part1 = mapping.dot3((cos_y * cos_z,
                                  sin_y * sin_x * cos_z - cos_x * sin_z,
                                  sin_y * cos_x * cos_z + sin_x * sin_z, 0.0))
            part2 = mapping.dot3((cos_y * sin_z,
                                  sin_y * sin_x * sin_z + cos_x * cos_z,
                                  sin_y * cos_x * sin_z - sin_x * cos_z, 0.0))
            part3 = mapping.dot3((-sin_y,
                                  cos_y * sin_x,
                                  cos_y * cos_x, 0.0))
        else:
            part1 = mapping.dot3((cos_y * cos_z, cos_y * sin_z, -sin_y, 0.0))
            part2 = mapping.dot3((sin_y * sin_x * cos_z - cos_x * sin_z,
                                  sin_y * sin_x * sin_z + cos_x * cos_z,
                                  cos_y * sin_x, 0.0))
            part3 = mapping.dot3((sin_y * cos_x * cos_z + sin_x * sin_z,
                                  sin_y * cos_x * sin_z - sin_x * cos_z,
                                  cos_y * cos_x, 0.0))
        return part1.combine4(part2, part3, self.node_item((0, 0, 0, 1)))

    def export_281(self):
        """ Export reworked node of Blender version 2.81+ """
        mapping = self.get_input_link('Vector')
        if not mapping:
            mapping = self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV
            })

        location = self.get_input_value('Location')
        scale = self.get_input_value('Scale')
        
        mapping_type = self.node.vector_type
        if mapping_type == 'POINT':
            return self.rotation(mapping * scale) + location
        elif mapping_type == 'TEXTURE':
            return self.rotation(mapping - location, transpose=True) / scale
        elif mapping_type == 'VECTOR':
            return self.rotation(mapping * scale)
        else:
            return (self.rotation(mapping / scale)).normalize()

    def export_280(self):
        """ Export node of Blender version 2.80 """
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
        if not (math.isclose(scale[0], 1.0) and
                math.isclose(scale[1], 1.0) and
                math.isclose(scale[2], 1.0)):
            # to match cycles "Texture" mapping type scale is used as a divider
            if self.node.vector_type == 'TEXTURE':
                mapping /= tuple(max(axis_scale, 0.001) for axis_scale in scale)
            else:
                mapping *= scale

        if self.node.use_min:
            mapping = mapping.min(tuple(self.node.min))

        if self.node.use_max:
            mapping = mapping.max(tuple(self.node.min))

        return mapping


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


class ShaderNodeCombineColor(NodeParser):
    """ Combine 3 input values to vector/color (v1, v2, v3, 0.0), accept input maps """
    def export(self):
        mode = self.node.mode

        value1 = self.get_input_value(0)
        value2 = self.get_input_value(1)
        value3 = self.get_input_value(2)

        res = value1.combine(value2, value3)

        if mode == 'HSL':
            return res.hsl_to_rgb()

        elif mode == 'HSV':
            return res.hsv_to_rgb()

        return res


class ShaderNodeSeparateColor(NodeParser):
    """ Split input value(color) to 3 separate values by RGB, HSV, HSL channels """
    def export(self):
        value = self.get_input_value(0)
        mode = self.node.mode
        socket = {'Red': 0, 'Green': 1, 'Blue': 2,
                  'Hue': 0, 'Saturation': 1, 'Value': 2, 'Lightness': 2,}[self.socket_out.name]

        if mode == 'HSL':
            return value.rgb_to_hsl().get_channel(socket)

        elif mode == 'HSV':
            return value.rgb_to_hsv().get_channel(socket)

        return value.get_channel(socket)


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

        if self.object and self.node.uv_map and self.object.type == 'MESH':
            mesh = self.object.data
            primary_uv = mesh.rpr.primary_uv_layer
            if primary_uv and self.node.uv_map == primary_uv.name:
                return self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                    pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV
                })

            # use secondary UV set if any available for the mesh
            if mesh.rpr.secondary_uv_layer(self.object):
                return self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
                    pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV1
                })

        return self.create_node(pyrpr.MATERIAL_NODE_INPUT_LOOKUP, {
            pyrpr.MATERIAL_INPUT_VALUE: pyrpr.MATERIAL_NODE_LOOKUP_UV
        })


class ShaderNodeVolumePrincipled(NodeParser):
    def export(self):
        # textures can be used by the RPR_MATERIAL_NODE_VOLUME shader node
        color = self.get_input_value('Color')
        density = self.get_input_value('Density')
        anisotropy = self.get_input_value('Anisotropy')
        absorption_color = self.get_input_scalar('Absorption Color')
        emission_strength = self.get_input_value('Emission Strength')
        blackbody_intensity = self.get_input_value('Blackbody Intensity')

        if emission_strength.is_zero() and not blackbody_intensity.is_zero():
            blackbody_tint = self.get_input_value('Blackbody Tint')
            temperature = self.get_input_scalar('Temperature')

            emission_color = blackbody_intensity * blackbody_tint * \
                             (*convert_kelvins_to_rgb(temperature.get_channel(0).data), 1.0)
        else:
            emission_color = self.get_input_value('Emission Color') * emission_strength

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_VOLUME, {
            pyrpr.MATERIAL_INPUT_EMISSION: emission_color,
            pyrpr.MATERIAL_INPUT_G: anisotropy,
            pyrpr.MATERIAL_INPUT_MULTISCATTER: True,
            pyrpr.MATERIAL_INPUT_SCATTERING: color * density,
            pyrpr.MATERIAL_INPUT_ABSORBTION: absorption_color * density,
        })

        # getting scalar data for hetero volume data since it does not work with textures
        color = self.get_input_scalar('Color')
        density = self.get_input_scalar('Density')
        emission_strength = self.get_input_scalar('Emission Strength')
        blackbody_intensity = self.get_input_scalar('Blackbody Intensity')
        density_attr = self.get_input_default('Density Attribute')
        temperature_attr = self.get_input_default('Temperature Attribute')

        # scalar emission values can be different from linked, make check again
        if emission_strength.is_zero() and not blackbody_intensity.is_zero():
            blackbody_tint = self.get_input_scalar('Blackbody Tint')
            temperature = self.get_input_scalar('Temperature')

            emission_color = blackbody_intensity * blackbody_tint * \
                             (*convert_kelvins_to_rgb(temperature.get_channel(0).data), 1.0)
        else:
            emission_color = self.get_input_scalar('Emission Color') * emission_strength

        # storing hetero volume data as an additional field 'data' of MaterialNode object
        rpr_node.data.data = {
            'color': tuple(color.get_channel(i).data for i in range(3)),
            'density': density.get_channel(0).data,
            'density_attr': density_attr.data,
            'emission_color': tuple(emission_color.get_channel(i).data for i in range(3)),
            'temperature_attr': temperature_attr.data,
        }

        return rpr_node

    def export_hybrid(self):
        return None

    def export_rpr2(self):
        def volume_export():
            if not self.object:
                return None

            density_attr = self.get_input_default('Density Attribute')
            density_grid_node = volume.create_grid_sampler_node(
                self.rpr_context, self.object, density_attr.data, 'density')

            if not density_grid_node:
                if self.object.type == 'VOLUME' or volume.get_smoke_modifier(self.object):
                    return self.create_node(pyrpr.MATERIAL_NODE_VOLUME, {pyrpr.MATERIAL_INPUT_DENSITY: 0.0})

                return None

            color = self.get_input_value('Color')
            density = self.get_input_value('Density')
            anisotropy = self.get_input_value('Anisotropy')
            emission_strength = self.get_input_value('Emission Strength')
            blackbody_intensity = self.get_input_value('Blackbody Intensity')

            color *= 0.99   # making color slightly less, because of issue
                            # that (1, 1, 1) color and higher disables emission

            rpr_node = self.create_node(pyrpr.MATERIAL_NODE_VOLUME, {
                pyrpr.MATERIAL_INPUT_DENSITY: density,
                pyrpr.MATERIAL_INPUT_G: anisotropy,
                pyrpr.MATERIAL_INPUT_MULTISCATTER: True,
                pyrpr.MATERIAL_INPUT_DENSITYGRID: density_grid_node,
                pyrpr.MATERIAL_INPUT_COLOR: color,
            })

            if enabled(emission_strength) or enabled(blackbody_intensity):
                # set emission grid
                if enabled(blackbody_intensity):
                    temperature_attr = self.get_input_default('Temperature Attribute')
                    emission_grid_node = volume.create_grid_sampler_node(
                        self.rpr_context, self.object, temperature_attr.data, 'temperature')
                else:
                    emission_grid_node = volume.create_grid_sampler_node(
                        self.rpr_context, self.object, 'flame', None)

                if emission_grid_node:
                    lookup_image = self.rpr_context.create_image_data(None,
                        np.array([1.0, 1.0, 1.0, 0.0, 0.0, 0.0], dtype=np.float32).reshape(-1, 1, 3))
                    emission_image_node = self.create_node(pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, {
                        pyrpr.MATERIAL_INPUT_DATA: lookup_image,
                        pyrpr.MATERIAL_INPUT_UV: emission_grid_node,
                        pyrpr.MATERIAL_INPUT_WRAP_U: pyrpr.IMAGE_WRAP_TYPE_CLAMP_TO_EDGE,
                        pyrpr.MATERIAL_INPUT_WRAP_V: pyrpr.IMAGE_WRAP_TYPE_CLAMP_TO_EDGE,
                    })

                    if enabled(blackbody_intensity):
                        temperature = self.get_input_value('Temperature')
                        blackbody_tint = self.get_input_value('Blackbody Tint')

                        blackbody_node = self.create_node(pyrpr.MATERIAL_NODE_BLACKBODY, {
                            pyrpr.MATERIAL_INPUT_KELVIN: temperature,
                            pyrpr.MATERIAL_INPUT_TEMPERATURE: 1.0,
                        })

                        emission = emission_image_node * blackbody_node * blackbody_intensity * \
                                   blackbody_tint

                        # additional multiplication to be corresponded with cycles
                        emission *= temperature * 0.005

                    else:
                        emission_color = self.get_input_value('Emission Color')

                        emission = emission_image_node * emission_color * emission_strength

                    rpr_node.set_input(pyrpr.MATERIAL_INPUT_EMISSION, emission)

            return rpr_node

        def base_export():
            color = self.get_input_value('Color')
            density = self.get_input_value('Density')
            anisotropy = self.get_input_value('Anisotropy')
            emission_strength = self.get_input_value('Emission Strength')
            blackbody_intensity = self.get_input_value('Blackbody Intensity')

            if emission_strength.is_zero() and not blackbody_intensity.is_zero():
                blackbody_tint = self.get_input_value('Blackbody Tint')
                temperature = self.get_input_scalar('Temperature')

                emission_color = blackbody_intensity * blackbody_tint * \
                                 (*convert_kelvins_to_rgb(temperature.get_channel(0).data), 1.0)
            else:
                emission_color = self.get_input_value('Emission Color') * emission_strength

            rpr_node = self.create_node(pyrpr.MATERIAL_NODE_VOLUME, {
                pyrpr.MATERIAL_INPUT_COLOR: color,
                pyrpr.MATERIAL_INPUT_DENSITY: density,
                pyrpr.MATERIAL_INPUT_EMISSION: emission_color,
                pyrpr.MATERIAL_INPUT_G: anisotropy,
                pyrpr.MATERIAL_INPUT_MULTISCATTER: True,
            })

            return rpr_node

        rpr_node = volume_export()

        if not rpr_node:
            rpr_node = base_export()

        return rpr_node


class ShaderNodeVolumeScatter(NodeParser):
    def export(self):
        color = self.get_input_value('Color')
        density = self.get_input_value('Density')
        anisotropy = self.get_input_value('Anisotropy')

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_VOLUME, {
            pyrpr.MATERIAL_INPUT_G: anisotropy,
            pyrpr.MATERIAL_INPUT_MULTISCATTER: True,
        })

        if isinstance(self.rpr_context, RPRContext2):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_COLOR, color)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_DENSITY, density)
        else:
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_SCATTERING, color * density)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_ABSORBTION, density)

        # getting scalar data for hetero volume data since it does not work with textures
        color = self.get_input_scalar('Color')
        density = self.get_input_scalar('Density')
        anisotropy = self.get_input_scalar('Anisotropy')

        # storing hetero volume data as an additional field 'data' of MaterialNode object
        rpr_node.data.data = {
            'color': color.data[:3],
            'density': density.get_channel(0).data,
            'anisotropy': anisotropy.get_channel(0).data,
        }

        return rpr_node

    def export_hybrid(self):
        return None

    def export_rpr2(self):
        color = self.get_input_value('Color')
        density = self.get_input_value('Density')
        anisotropy = self.get_input_value('Anisotropy')

        rpr_node = self.create_node(pyrpr.MATERIAL_NODE_VOLUME, {
            pyrpr.MATERIAL_INPUT_COLOR: color,
            pyrpr.MATERIAL_INPUT_DENSITY: density,
            pyrpr.MATERIAL_INPUT_G: anisotropy,
            pyrpr.MATERIAL_INPUT_MULTISCATTER: True,
        })

        # Heterovolumes additionally calculates grids and apply to rpr_node
        if not self.object:
            return rpr_node

        density_grid_node = volume.create_grid_sampler_node(self.rpr_context, self.object, 'density', None)
        if not density_grid_node:
            return rpr_node

        rpr_node.set_input(pyrpr.MATERIAL_INPUT_DENSITYGRID, density_grid_node)

        return rpr_node


class ShaderNodeVolumeInfo(NodeParser):
    def export(self):
        return None

    def export_rpr2(self):
        if not self.object:
            return None

        grid_node = volume.create_grid_sampler_node(self.rpr_context, self.object, self.socket_out.name, None)
        if not grid_node:
            return None

        lookup_image = self.rpr_context.create_image_data(
            None, np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0], dtype=np.float32).reshape(-1, 1, 3))

        return self.create_node(pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, {
            pyrpr.MATERIAL_INPUT_DATA: lookup_image,
            pyrpr.MATERIAL_INPUT_UV: grid_node,
            pyrpr.MATERIAL_INPUT_WRAP_U: pyrpr.IMAGE_WRAP_TYPE_CLAMP_TO_EDGE,
            pyrpr.MATERIAL_INPUT_WRAP_V: pyrpr.IMAGE_WRAP_TYPE_CLAMP_TO_EDGE,
        })


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
        # Follows code example for doing RGB transform from 
        # http://beesbuzz.biz/code/16-hsv-color-transforms

        color = self.get_input_value('Color')
        fac = self.get_input_value('Fac')
        hue = self.get_input_value('Hue') - 0.5
        saturation = self.get_input_value('Saturation')
        value = self.get_input_value('Value')

        vsu = value * saturation * hue.cos()
        vsw = value * saturation * hue.sin()

        color_r = color.get_channel(0)
        color_g = color.get_channel(1)
        color_b = color.get_channel(2)

        r = (.299 * value + .701 * vsu + .168 * vsw) * color_r
        r2 = (.587 * value - .587 * vsu + .330 * vsw) * color_g
        r3 = (.114 * value - .114 * vsu - .497 * vsw) * color_b
        r = r + r2 + r3

        g = (.299 * value - .299 * vsu - .328 * vsw) * color_r
        g2 = (.587 * value + .413 * vsu + .035 * vsw) * color_g
        g3 = (.114 * value - .114 * vsu + .292 * vsw) * color_b
        g = g + g2 + g3

        b = (.299 * value - .300 * vsu + 1.25 * vsw) * color_r
        b2 = (.587 * value - .588 * vsu - 1.05 * vsw) * color_g
        b3 = (.114 * value + .886 * vsu - .203 * vsw) * color_b
        b = b + b2 + b3

        rgb = r.combine(g, b)
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
        specular_color = self.get_input_value('Specular')  # this is color value
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
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_COLOR, base_color)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_WEIGHT, 1.0)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_ROUGHNESS, roughness)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_WEIGHT, 0.0)
        if enabled(normal):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_DIFFUSE_NORMAL, normal)

        # Specular
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_COLOR, specular_color)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_WEIGHT, 1.0)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_ROUGHNESS, roughness)

        if enabled(normal):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_REFLECTION_NORMAL, normal)

        # Emissive
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_EMISSION_COLOR, emissive_color)
        rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_EMISSION_WEIGHT, emissive_color.average_xyz())

        # Transparency
        if enabled(transparency):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_TRANSPARENCY, transparency)

        # Clear Coat
        if enabled(clearcoat):
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_COLOR, (1.0, 1.0, 1.0, 1.0))
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_WEIGHT, clearcoat)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_ROUGHNESS, clearcoat_roughness)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_THICKNESS, 0.0)
            rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_TRANSMISSION_COLOR, (0.0, 0.0, 0.0, 0.0))

            if enabled(clearcoat_normal):
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_NORMAL, clearcoat_normal)
            elif enabled(normal):
                rpr_node.set_input(pyrpr.MATERIAL_INPUT_UBER_COATING_NORMAL, normal)

        return rpr_node
