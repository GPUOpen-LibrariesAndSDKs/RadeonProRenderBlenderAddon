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

from rprblender.utils import is_rpr_active


class RPR_ShaderNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == "RPR"\
               and context.space_data.tree_type in ('ShaderNodeTree', 'RPRTreeType')


node_categories = [
    RPR_ShaderNodeCategory('RPR_INPUT', "Input", items=[
        NodeItem('ShaderNodeAmbientOcclusion'),
        NodeItem('ShaderNodeFresnel'),
        NodeItem('ShaderNodeLayerWeight'),
        NodeItem('ShaderNodeRGB'),
        NodeItem('ShaderNodeTexCoord'),
        NodeItem('ShaderNodeValue'),
        NodeItem('ShaderNodeNewGeometry'),
        NodeItem('ShaderNodeUVMap'),
        NodeItem('RPRShaderProceduralUVNode'),
        NodeItem('RPRShaderNodeLookup'),
    ],),
    RPR_ShaderNodeCategory('RPR_OUTPUT', "Output", items=[
        NodeItem('ShaderNodeOutputMaterial'),
    ],),
    RPR_ShaderNodeCategory('RPR_BLENDER_NODES', "Shader", items=[
        NodeItem('ShaderNodeBsdfPrincipled'),
        NodeItem('ShaderNodeBsdfHair'),
        NodeItem('ShaderNodeAddShader'),
        NodeItem('ShaderNodeMixShader'),
        NodeItem('ShaderNodeEmission'),
        NodeItem('ShaderNodeVolumePrincipled'),
        NodeItem('RPRShaderNodeUber'),
        NodeItem('RPRShaderNodePassthrough'),
        NodeItem('RPRShaderNodeLayered'),
    ]),
    RPR_ShaderNodeCategory("RPR_TEXTURES", "Texture", items=[
        NodeItem('ShaderNodeTexChecker'),
        NodeItem('ShaderNodeTexGradient'),
        NodeItem('ShaderNodeTexImage'),
        NodeItem('ShaderNodeTexNoise'),
        NodeItem('RPRTextureNodeLayered'),
    ],),
    RPR_ShaderNodeCategory('RPR_COLOR', "Color", items=[
        NodeItem('ShaderNodeBrightContrast'),
        NodeItem('ShaderNodeGamma'),
        NodeItem('ShaderNodeInvert'),
        NodeItem('ShaderNodeMixRGB'),
        NodeItem('ShaderNodeRGBCurve'),
        NodeItem('ShaderNodeHueSaturation'),
    ]),
    RPR_ShaderNodeCategory('RPR_VECTOR', "Vector", items=[
        NodeItem('ShaderNodeBump'),
        NodeItem('ShaderNodeDisplacement'),
        NodeItem('ShaderNodeMapping'),
        NodeItem('ShaderNodeNormal'),
        NodeItem('ShaderNodeNormalMap'),
    ]),
    RPR_ShaderNodeCategory('RPR_CONVERTER', "Converter", items=[
        NodeItem('ShaderNodeBlackbody'),
        NodeItem('ShaderNodeValToRGB'),
        NodeItem('ShaderNodeCombineXYZ'),
        NodeItem('ShaderNodeCombineRGB'),
        NodeItem('ShaderNodeCombineHSV'),
        NodeItem('ShaderNodeMath'),
        NodeItem('ShaderNodeRGBToBW'),
        NodeItem('ShaderNodeSeparateRGB'),
        NodeItem('ShaderNodeSeparateXYZ'),
        NodeItem('ShaderNodeSeparateHSV'),
        NodeItem('ShaderNodeVectorMath'),
        NodeItem('RPRValueNode_Math'),
    ]),
    RPR_ShaderNodeCategory('Layout', "Layout", items=[
        NodeItem('NodeReroute'),
    ])
]


def hide_cycles_and_eevee_poll(method):
    @classmethod
    def func(cls, context):
        return not is_rpr_active(context) and method(context)
    return func


from . import sockets
from . import rpr_nodes

register_classes, unregister_classes = bpy.utils.register_classes_factory([
    sockets.RPRSocketColor,
    sockets.RPRSocketFloat,
    sockets.RPRSocketWeight,
    sockets.RPRSocketWeightSoft,
    sockets.RPRSocketMin1Max1,
    sockets.RPRSocketLink,
    sockets.RPRSocketIOR,
    sockets.RPRSocket_Float_Min0_SoftMax10,
    sockets.RPRSocketAngle360,
    sockets.RPRSocketValue,

    rpr_nodes.RPRShaderNodeUber,
    rpr_nodes.RPRShaderNodeDiffuse,
    rpr_nodes.RPRShaderNodePassthrough,
    rpr_nodes.RPRShaderNodeBlend,
    rpr_nodes.RPRShaderNodeEmissive,
    rpr_nodes.RPRShaderNodeNormalMap,
    rpr_nodes.RPRShaderNodeBumpMap,
    rpr_nodes.RPRShaderNodeLookup,
    rpr_nodes.RPRShaderNodeImageTexture,
    rpr_nodes.RPRValueNode_Math,
    rpr_nodes.RPRShaderProceduralUVNode,
    rpr_nodes.RPRShaderNodeLayered,
    rpr_nodes.RPRTextureNodeLayered,
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
