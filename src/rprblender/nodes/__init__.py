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
from rprblender.utils import logging

from .sockets import classes

log = logging.Log(tag='nodes')


class MaterialError(Exception):
    pass

# have to put these after the Material Error
from .rpr_nodes import RPRShaderNodeUber_UI, RPRShaderNode
from .output_node import RPR_Node_Output


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
    #    NodeItem('ShaderNodeBlackbody'),
        NodeItem('ShaderNodeNewGeometry'),
    ],),
    RPR_ShaderNodeCategory('RPR_OUTPUT', "Output", items=[
        NodeItem('ShaderNodeOutputMaterial'),
    ],),
    RPR_ShaderNodeCategory("RPR_TEXTURES", "Texture", items=[
        NodeItem('ShaderNodeTexImage'),
        NodeItem('ShaderNodeTexChecker'),
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
    RPR_ShaderNodeCategory('RPR_VECTOR', "Vector", items=[
        NodeItem('ShaderNodeBump'),
        NodeItem('ShaderNodeNormalMap'),
    ]),
    RPR_ShaderNodeCategory('RPR_COLOR', "Color", items=[
        NodeItem('ShaderNodeInvert'),
        NodeItem('ShaderNodeBrightContrast'),
        NodeItem('ShaderNodeLightFalloff'),
        NodeItem('ShaderNodeGamma'),
        NodeItem('ShaderNodeMixRGB'),
    ]),
    # Temporary removing till it'll be working
    # RPR_ShaderNodeCategory('RPR_SHADER', "RPR Shader", items=[
    #     NodeItem('RPRShaderNodeUber'),
    # ])
]


def hide_cycles_and_eevee_poll(method):
    @classmethod
    def func(cls, context):
        return not is_rpr_active(context) and method(context)
    return func


old_shader_node_category_poll = None


classes += (RPRShaderNode, RPR_Node_Output, RPRShaderNodeUber_UI)
register_classes, unregister_classes = bpy.utils.register_classes_factory(classes)


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
