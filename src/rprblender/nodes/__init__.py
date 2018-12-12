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

from .sockets import classes
from .node_tree import RPR_NodeTree
from .output_node import RPR_Node_Output
from .uber_node import RPR_Node_Uber
from .rpr_nodes import RPRShadingNode

class RPR_ShaderNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == "RPR"\
               and context.space_data.tree_type in ('ShaderNodeTree', 'RPRTreeType')


node_categories = [
    RPR_ShaderNodeCategory('OUTPUT', "Output", items=[
        NodeItem('rpr_shader_node_output'),
    ]),
    RPR_ShaderNodeCategory('SHADER', "Shader", items=[
        NodeItem('rpr_shader_node_uber'),
    ])
]


classes += (RPR_NodeTree, RPRShadingNode, RPR_Node_Output, RPR_Node_Uber)
register_classes, unregister_classes = bpy.utils.register_classes_factory(classes)


# wrapper to hide the Cycles/Eevee nodes yet use the default Shader Editor
def hide_cycles_and_eevee_poll(method):
    @classmethod
    def func(cls, context):
        return not is_rpr_active(context) and method(context)
    return func


def register():
#    rpr_nodes.generate_types()
#    ShaderNodeCategory.poll = hide_cycles_and_eevee_poll(ShaderNodeCategory.poll)

    register_classes()

    register_node_categories("RPR_NODES", node_categories)


def unregister():
    unregister_node_categories("RPR_NODES")
    unregister_classes()
