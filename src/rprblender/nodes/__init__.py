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
import bpy
from nodeitems_utils import (
    NodeCategory,
    NodeItem,
    register_node_categories,
    unregister_node_categories,
)
from nodeitems_builtins import (
    ShaderNodeCategory,
)

from rprblender.utils import is_rpr_active, BLENDER_VERSION


class RPR_ShaderNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == "RPR"\
               and context.space_data.tree_type in ('ShaderNodeTree', 'RPRTreeType')


def sorted_items(items:list):
    items.sort(key=lambda x: x.label)
    return items


node_categories = [
    RPR_ShaderNodeCategory('RPR_INPUT', "Input", items=sorted_items([
        NodeItem('ShaderNodeAmbientOcclusion'),
        NodeItem('ShaderNodeFresnel'),
        NodeItem('ShaderNodeLayerWeight'),
        NodeItem('ShaderNodeObjectInfo'),
        NodeItem('ShaderNodeRGB'),
        NodeItem('ShaderNodeTexCoord'),
        NodeItem('ShaderNodeValue'),
        NodeItem('ShaderNodeNewGeometry'),
        NodeItem('ShaderNodeUVMap'),
        NodeItem('ShaderNodeVolumeInfo'),
        NodeItem('RPRShaderProceduralUVNode'),
        NodeItem('RPRShaderNodeLookup'),
        NodeItem('ShaderNodeBevel'),
        NodeItem('ShaderNodeHairInfo'),
    ])),
    RPR_ShaderNodeCategory('RPR_OUTPUT', "Output", items=sorted_items([
        NodeItem('ShaderNodeOutputMaterial'),
    ])),
    RPR_ShaderNodeCategory('RPR_BLENDER_NODES', "Shader", items=sorted_items([
        NodeItem('ShaderNodeBsdfPrincipled'),
        NodeItem('ShaderNodeBsdfHair'),
        NodeItem('ShaderNodeBsdfHairPrincipled'),
        NodeItem('ShaderNodeAddShader'),
        NodeItem('ShaderNodeMixShader'),
        NodeItem('ShaderNodeEmission'),
        NodeItem('ShaderNodeVolumePrincipled'),
        NodeItem('ShaderNodeVolumeScatter'),
        NodeItem('RPRShaderNodeUber'),
        NodeItem('RPRShaderNodePassthrough'),
        NodeItem('RPRShaderNodeLayered'),
        NodeItem('RPRShaderNodeToon'),
        NodeItem('RPRShaderNodeDoublesided'),
        NodeItem('ShaderNodeBsdfAnisotropic'),
        NodeItem('ShaderNodeBsdfDiffuse'),
        NodeItem('ShaderNodeBsdfGlass'),
        NodeItem('ShaderNodeBsdfGlossy'),
        NodeItem('ShaderNodeBsdfRefraction'),
        NodeItem('ShaderNodeBsdfTranslucent'),
        NodeItem('ShaderNodeBsdfTransparent'),
        NodeItem('ShaderNodeBsdfVelvet'),
        NodeItem('ShaderNodeSubsurfaceScattering'),
    ])),
    RPR_ShaderNodeCategory("RPR_TEXTURES", "Texture", items=sorted_items([
        NodeItem('ShaderNodeTexChecker'),
        NodeItem('ShaderNodeTexGradient'),
        NodeItem('ShaderNodeTexImage'),
        NodeItem('ShaderNodeTexNoise'),
        NodeItem('ShaderNodeTexVoronoi'),
        NodeItem('RPRTextureNodeLayered'),
    ])),
    RPR_ShaderNodeCategory('RPR_COLOR', "Color", items=sorted_items([
        NodeItem('ShaderNodeBrightContrast'),
        NodeItem('ShaderNodeGamma'),
        NodeItem('ShaderNodeInvert'),
        NodeItem("ShaderNodeMix", label="Mix Color",
                 settings={"data_type": "'RGBA'"}, poll=lambda cls: BLENDER_VERSION >= "3.4"),
        NodeItem('ShaderNodeMixRGB', poll=lambda cls: BLENDER_VERSION < "3.4"),
        NodeItem('ShaderNodeRGBCurve'),
        NodeItem('ShaderNodeHueSaturation'),
    ])),
    RPR_ShaderNodeCategory('RPR_VECTOR', "Vector", items=sorted_items([
        NodeItem('ShaderNodeBump'),
        NodeItem('ShaderNodeDisplacement'),
        NodeItem('ShaderNodeMapping'),
        NodeItem('ShaderNodeNormal'),
        NodeItem('ShaderNodeNormalMap'),
    ])),
    RPR_ShaderNodeCategory('RPR_CONVERTER', "Converter", items=sorted_items([
        NodeItem('ShaderNodeBlackbody'),
        NodeItem('ShaderNodeValToRGB'),
        NodeItem('ShaderNodeCombineXYZ'),
        NodeItem('ShaderNodeMapRange'),
        NodeItem('ShaderNodeMath'),
        NodeItem('ShaderNodeRGBToBW'),
        NodeItem('ShaderNodeSeparateXYZ'),
        NodeItem('ShaderNodeVectorMath'),
        NodeItem('RPRValueNode_Math'),
        NodeItem("ShaderNodeMix", poll=lambda cls: BLENDER_VERSION >= "3.4"),
        NodeItem('ShaderNodeSeparateColor', poll=lambda cls: BLENDER_VERSION >= "3.3"),
        NodeItem('ShaderNodeCombineColor', poll=lambda cls: BLENDER_VERSION >= "3.3"),
        NodeItem('ShaderNodeSeparateRGB', poll=lambda cls: BLENDER_VERSION < "3.3"),
        NodeItem('ShaderNodeSeparateHSV', poll=lambda cls: BLENDER_VERSION < "3.3"),
        NodeItem('ShaderNodeCombineRGB', poll=lambda cls: BLENDER_VERSION < "3.3"),
        NodeItem('ShaderNodeCombineHSV', poll=lambda cls: BLENDER_VERSION < "3.3"),
    ])),
    RPR_ShaderNodeCategory('Layout', "Layout", items=sorted_items([
        NodeItem('NodeReroute'),
        NodeItem('NodeFrame'),
    ]), )
]


def hide_cycles_and_eevee_poll(method):
    @classmethod
    def func(cls, context):
        return not is_rpr_active(context) and method(context)
    return func


from . import sockets
from . import rpr_nodes

register_classes, unregister_classes = bpy.utils.register_classes_factory([
    sockets.RPRSocketColorInterface,
    sockets.RPRSocketColor,
    sockets.RPRSocketFloatInterface,
    sockets.RPRSocketFloat,
    sockets.RPRSocketWeightInterface,
    sockets.RPRSocketWeight,
    sockets.RPRSocketWeightSoftInterface,
    sockets.RPRSocketWeightSoft,
    sockets.RPRSocketMin1Max1Interface,
    sockets.RPRSocketMin1Max1,
    sockets.RPRSocketLinkInterface,
    sockets.RPRSocketLink,
    sockets.RPRSocketIORInterface,
    sockets.RPRSocketIOR,
    sockets.RPRSocket_Float_Min0_SoftMax10Interface,
    sockets.RPRSocket_Float_Min0_SoftMax10,
    sockets.RPRSocketAngle360Interface,
    sockets.RPRSocketAngle360,
    sockets.RPRSocketValueInterface,
    sockets.RPRSocketValue,

    rpr_nodes.RPRShaderNodeUber,
    rpr_nodes.RPRShaderNodeDiffuse,
    rpr_nodes.RPRShaderNodePassthrough,
    rpr_nodes.RPRShaderNodeBlend,
    rpr_nodes.RPRShaderNodeDoublesided,
    rpr_nodes.RPRShaderNodeEmissive,
    rpr_nodes.RPRShaderNodeNormalMap,
    rpr_nodes.RPRShaderNodeBumpMap,
    rpr_nodes.RPRShaderNodeLookup,
    rpr_nodes.RPRShaderNodeImageTexture,
    rpr_nodes.RPRValueNode_Math,
    rpr_nodes.RPRShaderProceduralUVNode,
    rpr_nodes.RPRShaderNodeLayered,
    rpr_nodes.RPRTextureNodeLayered,
    rpr_nodes.RPRShaderNodeToon,
])


old_shader_node_category_poll = None


def register():
    # rpr_nodes.generate_types()

    # some nodes are hidden from plugins by Cycles itself(like Material Output), some we could not support.
    # thus we'll hide 'em all to show only selected set of supported Blender nodes
    global old_shader_node_category_poll
    old_shader_node_category_poll = ShaderNodeCategory.poll
    ShaderNodeCategory.poll = hide_cycles_and_eevee_poll(ShaderNodeCategory.poll)

    register_classes()
    register_node_categories("RPR_NODES", node_categories)


def unregister():
    if old_shader_node_category_poll and ShaderNodeCategory.poll is not old_shader_node_category_poll:
        ShaderNodeCategory.poll = old_shader_node_category_poll
    unregister_node_categories("RPR_NODES")
    unregister_classes()
