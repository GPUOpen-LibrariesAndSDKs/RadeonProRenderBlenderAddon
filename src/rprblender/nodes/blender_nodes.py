from .node_parser import NodeParser, get_rpr_val
import pyrpr
from rprblender.utils import image as image_utils

''' All parser classes should override NodeParser and override the 
    export() method if needed, or just set the input/rpr_node mapping '''


class ShaderNodeAmbientOcclusion(NodeParser):

    inputs = ['Color', 'Distance', 'samples']

    nodes = {
        "AO": {
            "type": "RPR_MATERIAL_NODE_AO_MAP",
            "params": {
                "radius": "inputs.Distance",
                "side": "inputs.inside"
            }
        },
        "Color": {
            "type": "RPR_MATERIAL_NODE_BLEND_VALUE",
            "params": {
                "color0": [0.0, 0.0, 0.0, 0.0],
                "color1": "inputs.Color",
                "weight": "nodes.AO"
            }
        }
    }
    
    def get_blender_node_inputs(self):
        ''' deal with inside vector being 1,0,0 or 0,0,0 '''
    
        input_vals = super(ShaderNodeAmbientOcclusion, self).get_blender_node_inputs()
        input_vals['inside'] = (-1.0, 0.0, 0.0, 0.0) if self.blender_node.inside else (1.0, 0.0, 0.0, 0.0)

        return input_vals


class ShaderNodeBrightContrast(NodeParser):

    inputs = ["Bright", "Contrast", "Image"]
    
    nodes = {
        "a": {
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "params": {
                "color0": "inputs.Contrast",
                "color1": [1.0, 1.0, 1.0, 1.0],
                "op": "RPR_MATERIAL_NODE_OP_ADD"
            }
        },
        "mul_contrast": {
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "params": {
                "color0": "inputs.Contrast",
                "color1": [0.5, 0.5, 0.5, 0.5],
                "op": "RPR_MATERIAL_NODE_OP_MUL"
            }
        },
        "b": {
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "params": {
                "color0": "inputs.Bright",
                "color1": "nodes.mul_contrast",
                "op": "RPR_MATERIAL_NODE_OP_SUB"
            }
        },
        "multiply": {
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "params": {
                "color0": "inputs.Image",
                "color1": "nodes.a",
                "op": "RPR_MATERIAL_NODE_OP_MUL"
            }
        },
        "add": {
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "params": {
                "color0": "nodes.multiply",
                "color1": "nodes.b",
                "op": "RPR_MATERIAL_NODE_OP_ADD"
            }
        },
        "Image": { # output
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "params": {
                "color0": "nodes.add",
                "color1": [0.0, 0.0, 0.0, 0.0],
                "op": "RPR_MATERIAL_NODE_OP_MAX"
            }
        }
    }


class ShaderNodeBsdfAnisotropic(NodeParser):

    inputs = ["Color", "Roughness", "Anisotropy", "Rotation", "Normal"]

    nodes = {
        "BSDF": {
            "type": "RPR_MATERIAL_NODE_MICROFACET_ANISOTROPIC_REFLECTION",
            "params": {
                "color": "inputs.Color",
                "roughness": "inputs.Roughness",
                "anisotropic": "inputs.Anisotropy",
                "rotation": "inputs.Rotation",
                "normal": "inputs.Normal"
            }
        }
    }


class ShaderNodeBsdfDiffuse(NodeParser):

    inputs = ["Color", "Roughness", "Normal"]

    nodes = {
        "BSDF": {
            "type": "RPR_MATERIAL_NODE_DIFFUSE",
            "params": {
                "color": "inputs.Color",
                "roughness": "inputs.Roughness",
                "normal": "inputs.Normal"
            }
        }
    }


class ShaderNodeBsdfGlass(NodeParser):

    inputs = ["Color", "Roughness", "Normal", "IOR"]

    nodes = {
        "BSDF": {
            "type": "RPR_MATERIAL_NODE_MICROFACET_REFRACTION",
            "params": {
                "color": "inputs.Color",
                "roughness": "inputs.Roughness",
                "normal": "inputs.Normal",
                "ior": "inputs.IOR"
            }
        }
    }


class ShaderNodeBsdfGlossy(NodeParser):

    inputs = ["Color", "Roughness", "Normal"]

    nodes = {
        "BSDF": {
            "type": "RPR_MATERIAL_NODE_MICROFACET",
            "params": {
                "color": "inputs.Color",
                "roughness": "inputs.Roughness",
                "normal": "inputs.Normal"
            }
        }
    }


class ShaderNodeBsdfRefraction(NodeParser):

    inputs = ["Color", "Roughness", "Normal", "IOR"]

    nodes = {
        "BSDF": {
            "type": "RPR_MATERIAL_NODE_MICROFACET_REFRACTION",
            "params": {
                "color": "inputs.Color",
                "roughness": "inputs.Roughness",
                "normal": "inputs.Normal",
                "ior": "inputs.IOR"
            }
        }
    }


class ShaderNodeBsdfTranslucent(NodeParser):

    inputs = ["Color", "Normal"]

    nodes = {
        "BSDF": {
            "type": "RPR_MATERIAL_NODE_DIFFUSE_REFRACTION",
            "params": {
                "color": "inputs.Color",
                "normal": "inputs.Normal"
            }
        }
    }


class ShaderNodeBsdfTransparent(NodeParser):

    inputs = ["Color"]

    nodes = {
        "BSDF": {
            "type": "RPR_MATERIAL_NODE_TRANSPARENT",
            "params": {
                "color": "inputs.Color",
            }
        }
    }


class ShaderNodeBsdfVelvet(NodeParser):

    inputs = ["Color", "Sigma"]

    nodes = {
        "BSDF": {
            "type": "RPRX_MATERIAL_UBER",
            "params": {
                "RPRX_UBER_MATERIAL_DIFFUSE_WEIGHT": 0.0,
                "RPRX_UBER_MATERIAL_REFLECTION_WEIGHT": 0.0,
                "RPRX_UBER_MATERIAL_SHEEN_WEIGHT": 1.0,
                "RPRX_UBER_MATERIAL_SHEEN_TINT": "inputs.Sigma",
                "RPRX_UBER_MATERIAL_SHEEN": "inputs.Color"
            }
        }
    }


class ShaderNodeEmission(NodeParser):
    inputs = ["Color", "Strength"]

    nodes =  {
        "multiply": {
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "params": {
                "color0": "inputs.Color",
                "color1": "inputs.Strength",
                "op": "RPR_MATERIAL_NODE_OP_MUL"
            }
        },
        "Emission": {
            "type": "RPR_MATERIAL_NODE_EMISSIVE",
            "params": {
                "color": "nodes.multiply"
            }
        }
    }


class ShaderNodeFresnel(NodeParser):
    inputs =["IOR", "Normal"]

    nodes = {
        "Fac": {
            "type": "RPR_MATERIAL_NODE_FRESNEL",
            "params": {
                "ior": "inputs.IOR",
                "normal": "inputs.Normal"
            }
        }
    }


class ShaderNodeGamma(NodeParser):
    inputs =["Image", "Gamma"]

    nodes = {
        "Image": {
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "params": {
                "color0": "inputs.Image",
                "color1": "inputs.Gamma",
                "op": "RPR_MATERIAL_NODE_OP_POW"
            }
        }
    }


class ShaderNodeInvert(NodeParser):
    inputs = ["Factor", "Color"]

    nodes = {
        "invert": {
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "params": {
                "color0": [1.0, 1.0, 1.0, 1.0],
                "color1": "inputs.Color",
                "op": "RPR_MATERIAL_NODE_OP_SUB"
            }
        },
        "Color": {
            "type": "RPR_MATERIAL_NODE_BLEND_VALUE",
            "params": {
                "color0": "nodes.invert",
                "color1": "inputs.color",
                "weight": "inputs.factor"
            }
        }
    }

class ShaderNodeBump(NodeParser):
    pass # TODO


class ShaderNodeSubsurfaceScattering(NodeParser):
    inputs = ["Color", "Scale", "Radius"]

    nodes = {
        "multiply": {
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "params": {
                "color0": "inputs.Scale",
                "color1": "inputs.Radius",
                "op": "RPR_MATERIAL_NODE_OP_MUL"
            }
        },
        "BSSRDF": {
            "type": "RPRX_MATERIAL_UBER",
            "params": {
                "RPRX_UBER_MATERIAL_DIFFUSE_WEIGHT": 1.0,
                "RPRX_UBER_MATERIAL_REFLECTION_WEIGHT": 0.0,
                "RPRX_UBER_MATERIAL_BACKSCATTER_WEIGHT": 1.0,
                "RPRX_UBER_MATERIAL_BACKSCATTER_COLOR": [1.0, 1.0, 1.0, 1.0],
                "RPRX_UBER_MATERIAL_SSS_WEIGHT": 1.0,
                "RPRX_UBER_MATERIAL_SSS_SCATTER_COLOR": "inputs.Color",
                "RPRX_UBER_MATERIAL_SSS_SCATTER_DISTANCE": "nodes.multiply"
            }
        }
    }


class ShaderNodeTexChecker(NodeParser):

    inputs = ["Scale", "Vector", "Color1", "Color2"]
    nodes = {
        "multiply": {
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "params": {
                "color0": "inputs.Scale",
                "color1": "inputs.Vector",
                "op": "RPR_MATERIAL_NODE_OP_MUL"
            }
        },
        "Fac": {
            "type": "RPR_MATERIAL_NODE_CHECKER_TEXTURE",
            "params": {
                "uv": "nodes.multiply"
            }
        },
        "Color": {
            "type": "RPR_MATERIAL_NODE_BLEND_VALUE",
            "params": {
                "color0": "inputs.Color1",
                "color1": "inputs.Color2",
                "weight": "nodes.Fac"
            }
        }
    }

    def get_blender_node_inputs(self):
        ''' deal vector is disconeected '''
    
        input_vals = super(ShaderNodeTexChecker, self).get_blender_node_inputs()
        node_key = self.get_subnode_key('Vector')
        node = self.material_exporter.create_rpr_node('RPR_MATERIAL_NODE_INPUT_LOOKUP', node_key)
        input_vals['Vector'] = node
        node.set_input('value', pyrpr.MATERIAL_NODE_LOOKUP_UV)

        return input_vals


class ShaderNodeTexImage(NodeParser):
    inputs = ["Vector"]
    nodes = {
        "Color": {
            "type": "RPR_MATERIAL_NODE_IMAGE_TEXTURE",
            "params": {
                "data": "inputs.image",
                "uv": "inputs.Vector"
            }
        }
    }

    def get_blender_node_inputs(self):
        ''' deal vector is disconnected and get image data'''
    
        input_vals = super(ShaderNodeTexImage, self).get_blender_node_inputs()
        blender_node = self.blender_node

        if not blender_node.inputs['Vector'].is_linked:
            node_key = self.get_subnode_key('Vector')
            input_vals['Vector'] = self.material_exporter.create_rpr_node('RPR_MATERIAL_NODE_LOOKUP_UV', node_key)


        if blender_node.image:
            try:
                rpr_image = image_utils.get_rpr_image(self.material_exporter.rpr_context, blender_node.image)
                # set sRGB for color space
                if blender_node.color_space == 'COLOR':
                    rpr_image.set_gamma(2.2)

                # image wrap
                wrap_mapping = {'REPEAT': 'RPR_IMAGE_WRAP_TYPE_REPEAT',
                                'EXTEND': 'RPR_IMAGE_WRAP_TYPE_CLAMP_TO_EDGE', 
                                'CLIP': 'RPR_IMAGE_WRAP_TYPE_CLAMP_TO_ZERO'}
                rpr_image.set_wrap(get_rpr_val(wrap_mapping[blender_node.extension]))

            except ValueError as e:  # texture loading error, return "Texture Error/Absence" image
                log.error("Image error: {}".format(e))
                rpr_image = ERROR_COLOR 
            
            input_vals['image'] = rpr_image
        return input_vals

class ShaderNodeBsdfPrincipled(NodeParser):
    inputs = ["Base Color", "Roughness", 
             "Subsurface", 'Subsurface Radius', 'Subsurface Color', 
             'Metallic', 'Specular', 'Specular Tint', 'Anisotropic', 'Anisotropic Rotation', 
             'Clearcoat', 'Clearcoat Roughness', 
             'Sheen', 'Sheen Tint', 
             'Transmission', 'IOR', 'Transmission Roughness', 
             'Normal', 'Clearcoat Normal', 'Tangent']

    nodes = {
        "is_glass": {
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "params": {
                "color0": [1.0, 1.0, 1.0, 1.0],
                "color1": "inputs.Transmission",
                "op": "RPR_MATERIAL_NODE_OP_SUB"
            }
        },
        "sss_radius_max": {
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "params": {
                "color0": [0.0001, 0.0001, 0.0001, 0.0001],
                "color1": "inputs.Subsurface Radius",
                "op": "RPR_MATERIAL_NODE_OP_MAX"
            }
        },
        "BSDF": {
            "type": "RPRX_MATERIAL_UBER",
            "params": {
                "RPRX_UBER_MATERIAL_DIFFUSE_WEIGHT": "nodes.is_glass",
                "RPRX_UBER_MATERIAL_DIFFUSE_COLOR": "inputs.Base Color",
                "RPRX_UBER_MATERIAL_DIFFUSE_ROUGHNESS": "inputs.Roughness",
                "RPRX_UBER_MATERIAL_BACKSCATTER_WEIGHT": "inputs.Subsurface",
                "RPRX_UBER_MATERIAL_BACKSCATTER_COLOR": [1.0, 1.0, 1.0, 1.0],

                "RPRX_UBER_MATERIAL_REFLECTION_WEIGHT": "inputs.Specular",
                "RPRX_UBER_MATERIAL_REFLECTION_COLOR": "inputs.Base Color",
                # what should we do with specular tint ? 
                "RPRX_UBER_MATERIAL_REFLECTION_MODE": "RPRX_UBER_MATERIAL_REFLECTION_MODE_METALNESS",
                "RPRX_UBER_MATERIAL_REFLECTION_METALNESS": "inputs.Metallic",
                "RPRX_UBER_MATERIAL_REFLECTION_ROUGHNESS": "inputs.Roughness",
                "RPRX_UBER_MATERIAL_REFLECTION_ANISOTROPY": "inputs.Anisotropic",
                "RPRX_UBER_MATERIAL_REFLECTION_ANISOTROPY_ROTATION": "inputs.Anisotropic Rotation",

                "RPRX_UBER_MATERIAL_COATING_WEIGHT": "inputs.Clearcoat",
                "RPRX_UBER_MATERIAL_COATING_COLOR": [1.0, 1.0, 1.0, 1.0],
                "RPRX_UBER_MATERIAL_COATING_ROUGHNESS": "inputs.Clearcoat Roughness",
                "RPRX_UBER_MATERIAL_COATING_MODE": "RPRX_UBER_MATERIAL_COATING_MODE_PBR",
                "RPRX_UBER_MATERIAL_COATING_IOR": "inputs.IOR", # this maybe should be hardcoded

                "RPRX_UBER_MATERIAL_SHEEN_WEIGHT": "inputs.Sheen",
                "RPRX_UBER_MATERIAL_SHEEN": "inputs.Base Color",
                "RPRX_UBER_MATERIAL_SHEEN_TINT": "inputs.Sheen Tint",

                "RPRX_UBER_MATERIAL_SSS_WEIGHT": "inputs.Subsurface",
                "RPRX_UBER_MATERIAL_SSS_SCATTER_COLOR": "inputs.Subsurface Color",
                "RPRX_UBER_MATERIAL_SSS_SCATTER_DISTANCE": "nodes.sss_radius_max",
                "RPRX_UBER_MATERIAL_SSS_MULTISCATTER": 0,

                "RPRX_UBER_MATERIAL_REFRACTION_WEIGHT": "inputs.Transmission",
                "RPRX_UBER_MATERIAL_REFRACTION_COLOR": "inputs.Base Color",
                "RPRX_UBER_MATERIAL_REFRACTION_ROUGHNESS": "inputs.Transmission Roughness",
                "RPRX_UBER_MATERIAL_REFRACTION_IOR": "inputs.IOR",
                "RPRX_UBER_MATERIAL_REFRACTION_THIN_SURFACE": 0, # check?
                "RPRX_UBER_MATERIAL_REFRACTION_CAUSTICS": 0, # I think this is right.

                "RPRX_UBER_MATERIAL_DIFFUSE_NORMAL": "inputs.Normal",
                "RPRX_UBER_MATERIAL_REFLECTION_NORMAL": "inputs.Normal",
                "RPRX_UBER_MATERIAL_REFRACTION_NORMAL": "inputs.Normal",
                "RPRX_UBER_MATERIAL_COATING_NORMAL": "inputs.Clearcoat Normal",

            }
        }
    }


class ShaderNodeNewGeometry(NodeParser):
    ''' this is the "Geometry" node '''

    nodes = {
        "Position": {
            "type": "RPR_MATERIAL_NODE_INPUT_LOOKUP",
            "params": {
                "value": "RPR_MATERIAL_NODE_LOOKUP_P",
            }
        },
        "Normal": {
            "type": "RPR_MATERIAL_NODE_INPUT_LOOKUP",
            "params": {
                "value": "RPR_MATERIAL_NODE_LOOKUP_N",
            }
        },
        "Incoming": {
            "type": "RPR_MATERIAL_NODE_INPUT_LOOKUP",
            "params": {
                "value": "RPR_MATERIAL_NODE_LOOKUP_INVEC",
            }
        }
    }


class ShaderNodeAddShader(NodeParser):
    inputs = [0,1] # blender confusingly has inputs with the same name. 
    
    nodes = {
        "Shader": {
            "type": "RPR_MATERIAL_NODE_ADD",
            "params": {
                "color0": "inputs.0",
                "color1": "inputs.1",
            }
        }
    }


class ShaderNodeTexCoord(NodeParser):
    
    nodes = {
        "Generated": {
            "type": "RPR_MATERIAL_NODE_INPUT_LOOKUP",
            "params": {
                "value": "RPR_MATERIAL_NODE_LOOKUP_P",
            }
        },
        "Normal": {
            "type": "RPR_MATERIAL_NODE_INPUT_LOOKUP",
            "params": {
                "value": "RPR_MATERIAL_NODE_LOOKUP_N",
            }
        },
        "UV": {
            "type": "RPR_MATERIAL_NODE_INPUT_LOOKUP",
            "params": {
                "value": "RPR_MATERIAL_NODE_LOOKUP_UV",
            }
        }
    }

class ShaderNodeLightFalloff(NodeParser):
    ''' we don't actually do light falloff in RPR.  
        So we're mainly going to pass through "strength" '''
    inputs = ['Strength']

    def export(self, socket):
        return self.get_blender_node_inputs()['Strength']


mix_types_nodes = {'ADD':
                        {
                        "add": {
                            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
                            "params": {
                                "color0": "inputs.1",
                                "color1": "inputs.2",
                                "op": "RPR_MATERIAL_NODE_OP_ADD"
                            }
                        },
                        "Color": {
                            "type": "RPR_MATERIAL_NODE_BLEND_VALUE",
                            "params": {
                                "color0": "inputs.1",
                                "color1": "nodes.add",
                                "weight": "inputs.Fac"
                            }
                        }},
                    'MULTIPLY': {
                        "mul": {
                            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
                            "params": {
                                "color0": "inputs.1",
                                "color1": "inputs.2",
                                "op": "RPR_MATERIAL_NODE_OP_MUL"
                            }
                        },
                        "Color": {
                            "type": "RPR_MATERIAL_NODE_BLEND_VALUE",
                            "params": {
                                "color0": "inputs.1",
                                "color1": "nodes.mul",
                                "weight": "inputs.Fac"
                            }
                        }},
                    'SUBTRACT': {
                        "sub": {
                            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
                            "params": {
                                "color0": "inputs.1",
                                "color1": "inputs.2",
                                "op": "RPR_MATERIAL_NODE_OP_SUB"
                            }
                        },
                        "Color": {
                            "type": "RPR_MATERIAL_NODE_BLEND_VALUE",
                            "params": {
                                "color0": "inputs.1",
                                "color1": "nodes.sub",
                                "weight": "inputs.Fac"
                            }
                        }},
                    'DIVIDE': {
                        "div": {
                            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
                            "params": {
                                "color0": "inputs.1",
                                "color1": "inputs.2",
                                "op": "RPR_MATERIAL_NODE_OP_DIV"
                            }
                        },
                        "Color": {
                            "type": "RPR_MATERIAL_NODE_BLEND_VALUE",
                            "params": {
                                "color0": "nodes.div",
                                "color1": "inputs.1",
                                "weight": "inputs.Fac"
                            }
                        }},
                    'DIFFERENCE': {
                        "sub": {
                            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
                            "params": {
                                "color0": "inputs.1",
                                "color1": "inputs.2",
                                "op": "RPR_MATERIAL_NODE_OP_SUB"
                            }
                        },
                        "abs": {
                            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
                            "params": {
                                "color0": "nodes.sub",
                                "op": "RPR_MATERIAL_NODE_OP_ABS"
                            }
                        },
                        "Color": {
                            "type": "RPR_MATERIAL_NODE_BLEND_VALUE",
                            "params": {
                                "color0": "inputs.1",
                                "color1": "nodes.abs",
                                "weight": "inputs.Fac"
                            }
                        }},
                    'DARKEN': {
                        "min": {
                            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
                            "params": {
                                "color0": "inputs.1",
                                "color1": "inputs.2",
                                "op": "RPR_MATERIAL_NODE_OP_MIN"
                            }
                        },
                        "Color": {
                            "type": "RPR_MATERIAL_NODE_BLEND_VALUE",
                            "params": {
                                "color0": "nodes.min",
                                "color1": "inputs.1",
                                "weight": "inputs.Fac"
                            }
                        }},
                    'LIGHT': {
                        "mul": {
                            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
                            "params": {
                                "color0": "inputs.1",
                                "color1": "inputs.Fac",
                                "op": "RPR_MATERIAL_NODE_OP_MUL"
                            }
                        },
                        "Color": {
                            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
                            "params": {
                                "color0": "nodes.mul",
                                "color1": "inputs.1",
                                "op": "RPR_MATERIAL_NODE_OP_MAX"
                            }
                        }},
                   'MIX': {
                        "Color": {
                            "type": "RPR_MATERIAL_NODE_BLEND_VALUE",
                            "params": {
                                "color0": "inputs.1",
                                "color1": "inputs.2",
                                "weight": "inputs.Fac"
                            }
                        }}
                }

class ShaderNodeMixRGB(NodeParser):
    inputs = ['Fac', 1, 2]

    def export(self, socket):
        ''' this makes the self.nodes dict dynamically based on mix type '''

        # we need to do different mix nodes based on mode
        mix_type = self.blender_node.blend_type
        if mix_type in mix_types_nodes:
            self.nodes = mix_types_nodes[mix_type]
        else:
            log.warn("Unknown mix type {} on node: {}.  Defaulting to mix".format(mix_type, self.blender_node.name))
            self.nodes = mix_types_nodes['MIX']


        if self.blender_node.use_clamp:
            self.self.blender_nodes['op'] = self.blender_nodes['Color']
            self.blender_nodes['min_clamp'] = {
                            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
                            "params": {
                                "color0": "nodes.op",
                                "color1": [0.0, 0.0, 0.0, 0.0],
                                "op": "RPR_MATERIAL_NODE_OP_MIN"
                            }
                        }
            self.blender_nodes['Color'] = {
                            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
                            "params": {
                                "color0": "nodes.op",
                                "color1": [1.0, 1.0, 1.0, 1.0],
                                "op": "RPR_MATERIAL_NODE_OP_MAX"
                            }
                        }
        return super(ShaderNodeMixRGB, self).export(socket)


blender_node_parsers = {
    'ShaderNodeAmbientOcclusion': ShaderNodeAmbientOcclusion,
    'ShaderNodeBrightContrast': ShaderNodeBrightContrast,
    'ShaderNodeBsdfAnisotropic': ShaderNodeBsdfAnisotropic,
    'ShaderNodeBsdfDiffuse': ShaderNodeBsdfDiffuse,
    'ShaderNodeBsdfGlass': ShaderNodeBsdfGlass,
    'ShaderNodeBsdfGlossy': ShaderNodeBsdfGlossy,
    'ShaderNodeBsdfRefraction': ShaderNodeBsdfRefraction,
    'ShaderNodeBsdfTranslucent': ShaderNodeBsdfTranslucent,
    'ShaderNodeBsdfTransparent': ShaderNodeBsdfTransparent,
    'ShaderNodeBsdfVelvet': ShaderNodeBsdfVelvet,
    #'ShaderNodeBump'
    'ShaderNodeEmission': ShaderNodeEmission,
    'ShaderNodeFresnel': ShaderNodeFresnel,
    'ShaderNodeGamma': ShaderNodeGamma,
    'ShaderNodeInvert': ShaderNodeInvert,
    'ShaderNodeSubsurfaceScattering': ShaderNodeSubsurfaceScattering,
    'ShaderNodeTexChecker': ShaderNodeTexChecker,
    'ShaderNodeTexImage': ShaderNodeTexImage,
    'ShaderNodeBsdfPrincipled': ShaderNodeBsdfPrincipled,
    'ShaderNodeNewGeometry': ShaderNodeNewGeometry,
    'ShaderNodeAddShader': ShaderNodeAddShader,
    'ShaderNodeTexCoord': ShaderNodeTexCoord, 
    'ShaderNodeLightFalloff': ShaderNodeLightFalloff,
    'ShaderNodeMixRGB': ShaderNodeMixRGB

}
