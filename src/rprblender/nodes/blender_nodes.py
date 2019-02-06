import json
import os

import pyrpr
import pyrprx
from rprblender.utils import logging
# from .export import export_blender_node


log = logging.Log(tag="NodeExport")


''' Layout of meta data for nodes is SAME for blender nodes as RPR ones:
'''

def convert_blender_node(blender_node):
    ''' This function gets the converter json mapping and runs the rpr conversion'''
    if not mapping:
        load_mapping()

    blender_node_name = blender_node.__name__.split('.')[-1]
    if blender_node_name not in mapping:
        print("RPR can't convert this blender node " + blender_node)
        return

    export_blender_node(blender_node, mapping[blender_node_name])


def load_mapping():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    config_dir = os.path.join(dir_path, 'blender_nodes')
    for f in os.listdir(config_dir):
        with open(os.path.join(config_dir, f), 'r') as json_file:
            mapping[os.path.splitext(f)][0] = json.load(json_file)
            node_name = json_data.keys()[0]


bsdf_diffuse_rules = {
    "name": "ShaderNodeBsdfDiffuse",

    "inputs": {
        "color": {
            "type": "color",
            "label": "Color",
        },
        "roughness": {
            "type": "float",
            "label": "Roughness",
        }
    },

    "outputs": {
        "BSDF": {
            "type": "shader",
            "node": "diffuse"
        }
    },

    "nodes": {
        "diffuse": {
            "name": "diffuse",
            "type": "RPR_MATERIAL_NODE_DIFFUSE",
            "inputs": {
                "color": "inputs.color",
                "roughness": "inputs.roughness"
            }
        }
    }
}

bsdf_glossy_rules = {
    "name": "ShaderNodeBsdfGlossy",

    "inputs": {
        "color": {
            "type": "color",
            "label": "Color",
        },
        "roughness": {
            "type": "float",
            "label": "Roughness",
        }
    },

    "outputs": {
        "BSDF": {
            "type": "shader",
            "node": "uber"
        }
    },

    "nodes": {
        "reflection": {
            "name": "reflection",
            "type": "RPR_MATERIAL_NODE_REFLECTION",
            "inputs": {
                "color": "inputs.color",
            }
        },
        "uber": {
            "name": "uber",
            "type": "RPRX_MATERIAL_UBER",
            "inputs": {
                "RPRX_UBER_MATERIAL_DIFFUSE_WEIGHT": [0.0, 0.0, 0.0, 0.0],
                "RPRX_UBER_MATERIAL_REFLECTION_WEIGHT": [1.0, 1.0, 1.0, 1.0],
                "RPRX_UBER_MATERIAL_REFLECTION_MODE": pyrprx.UBER_MATERIAL_REFLECTION_MODE_METALNESS,
                "RPRX_UBER_MATERIAL_REFLECTION_METALNESS": [1.0, 1.0, 1.0, 1.0],

                "RPRX_UBER_MATERIAL_REFLECTION_COLOR": "inputs.color",
                "RPRX_UBER_MATERIAL_REFLECTION_ROUGHNESS": "inputs.roughness"
            }
        }
    }
}

bsdf_transparent_rules = {
    "name": "ShaderNodeBsdfTransparent",

    "inputs": {
        "color": {
            "type": "color",
            "label": "Color",
        },
    },

    "outputs": {
        "BSDF": {
            "type": "shader",
            "node": "transparent"
        }
    },

    "nodes": {
        "transparent": {
            "name": "diffuse",
            "type": "RPR_MATERIAL_NODE_TRANSPARENT",
            "inputs": {
                "color": "inputs.color",
            }
        }
    }
}

emission_rules = {
    "name": "ShaderNodeEmission",

    "inputs": {
        "color": {
            "type": "color",
            "label": "Color",
        },
        "strength": {
            "type": "float",
            "label": "Strength",
        }
    },

    "outputs": {
        "Emission": {
            "type": "shader",
            "label": "Emission",
            "node": "uber"
        },
    },

    "nodes": {
        "multiply": {
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "inputs": {
                "op": pyrpr.MATERIAL_NODE_OP_MUL,
                "color0": "inputs.color",
                "color1": "inputs.strength",
            },
        },
        "uber": {
            'name': "uber",
            'type': "RPRX_MATERIAL_UBER",
            'inputs': {
                "RPRX_UBER_MATERIAL_EMISSION_WEIGHT": [1.0, 1.0, 1.0, 1.0],

                "RPRX_UBER_MATERIAL_EMISSION_COLOR": "nodes.multiply",  # "inputs.color",  # 'nodes.multiply'
                "RPRX_UBER_MATERIAL_EMISSION_MODE": pyrprx.UBER_MATERIAL_EMISSION_MODE_DOUBLESIDED
            },
        },
    }
}

vector_bump_rules = {
    "name": "ShaderNodeBump",

    "inputs": {
        "height": {
            "type": "color",
            "label": "Height",
        },
        "strength": {
            "type": "float",
            "label": "Strength",
        },
        "distance": {
            "type": "float",
            "label": "Distance",
        }
    },

    "outputs": {
        "Normal": {
            "type": "noncolor",
            "node": "bump"
        }
    },

    "nodes": {
        "multiply": {
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "inputs": {
                "op": pyrpr.MATERIAL_NODE_OP_MUL,
                "color0": "inputs.strength",
                "color1": "inputs.distance",
            },
        },
        "bump": {
            "name": "bump_map",
            "type": "RPR_MATERIAL_NODE_BUMP_MAP",
            "inputs": {
                "color": "inputs.height",
                "bumpscale": "nodes.multiply",
            }
        }
    }
}

vector_normal_map_rules = {
    "name": "ShaderNodeNormalMap",

    "inputs": {
        "color": {
            "type": "color",
            "label": "Color",
        },
    },

    "outputs": {
        "Normal": {
            "type": "noncolor",
            "node": "normal"
        }
    },

    "nodes": {
        "normal": {
            "name": "normal_map",
            "type": "RPR_MATERIAL_NODE_NORMAL_MAP",
            "inputs": {
                "color": "inputs.color",
            }
        }
    }
}

color_invert_rules = {
    "name": "ShaderNodeInvert",

    "inputs": {
        "color": {
            "type": "color",
            "label": "Color",
        },
    },

    "outputs": {
        "Color": {
            "type": "color",
            "node": "sub"
        }
    },

    "nodes": {
        "sub": {
            "name": "arithmetic_sub",
            "type": "RPR_MATERIAL_NODE_ARITHMETIC",
            "inputs": {
                "op": pyrpr.MATERIAL_NODE_OP_SUB,
                "color0": 1.0,
                "color1": "inputs.color",
            }
        }
    }
}

class NodeExportRules:
    pass


class MaterialNodeExportRules:
    pass


def parse_export_nodes_rules():
    log("parse_export_nodes_rules")
    # for each entry
    #   replace constant names by constants values/references
