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
        NodeItem('ShaderNodeRGB'),
        NodeItem('ShaderNodeTexCoord'),
        NodeItem('ShaderNodeValue'),
        NodeItem('ShaderNodeNewGeometry'),
    ],),
    RPR_ShaderNodeCategory('RPR_OUTPUT', "Output", items=[
        NodeItem('ShaderNodeOutputMaterial'),
    ],),
    RPR_ShaderNodeCategory('RPR_BLENDER_NODES', "Shader", items=[
        NodeItem('ShaderNodeBsdfPrincipled'),
        NodeItem('ShaderNodeAddShader'),
        # one could make the argument we don't want people "creating" these
        NodeItem('ShaderNodeBsdfAnisotropic'),
        NodeItem('ShaderNodeBsdfDiffuse'),
        NodeItem('ShaderNodeBsdfGlass'),
        NodeItem('ShaderNodeBsdfGlossy'),
        NodeItem('ShaderNodeBsdfRefraction'),
        NodeItem('ShaderNodeBsdfTranslucent'),
        NodeItem('ShaderNodeBsdfTransparent'),
        NodeItem('ShaderNodeBsdfVelvet'),
        NodeItem('ShaderNodeMixShader'),
        NodeItem('ShaderNodeEmission'),
        NodeItem('ShaderNodeSubsurfaceScattering'),
    ]),
    RPR_ShaderNodeCategory("RPR_TEXTURES", "Texture", items=[
        NodeItem('ShaderNodeTexChecker'),
        NodeItem('ShaderNodeTexImage'),
        NodeItem('ShaderNodeTexNoise'),
    ],),
    RPR_ShaderNodeCategory('RPR_COLOR', "Color", items=[
        NodeItem('ShaderNodeBrightContrast'),
        NodeItem('ShaderNodeGamma'),
        NodeItem('ShaderNodeInvert'),
        NodeItem('ShaderNodeMixRGB'),
        NodeItem('ShaderNodeRGBCurve'),
    ]),
    RPR_ShaderNodeCategory('RPR_VECTOR', "Vector", items=[
        NodeItem('ShaderNodeBump'),
        NodeItem('ShaderNodeMapping'),
        NodeItem('ShaderNodeNormalMap'),
    ]),
    RPR_ShaderNodeCategory('RPR_CONVERTER', "Converter", items=[
        NodeItem('ShaderNodeBlackbody'),
        NodeItem('ShaderNodeValToRGB'),
        NodeItem('ShaderNodeCombineXYZ'),
        NodeItem('ShaderNodeCombineRGB'),
        NodeItem('ShaderNodeMath'),
        NodeItem('ShaderNodeRGBToBW'),
        NodeItem('ShaderNodeSeparateRGB'),
        NodeItem('ShaderNodeSeparateXYZ'),
        NodeItem('ShaderNodeVectorMath'),
        NodeItem('RPRValueNode_Math'),
    ]),
    RPR_ShaderNodeCategory('RPR_SHADER', "RPR Shader", items=[
        NodeItem('RPRShaderNodeUber'),
        # temporary disable this diffuse node
        # NodeItem('RPRShaderNodeDiffuse'),
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
    rpr_nodes.RPRShaderNodeBlend,
    rpr_nodes.RPRShaderNodeEmissive,
    rpr_nodes.RPRShaderNodeNormalMap,
    rpr_nodes.RPRShaderNodeBumpMap,
    rpr_nodes.RPRShaderNodeLookup,
    rpr_nodes.RPRShaderNodeImageTexture,
    rpr_nodes.RPRValueNode_Math,
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
