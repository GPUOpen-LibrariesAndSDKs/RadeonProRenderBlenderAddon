import bpy

from .rpr_nodes import RPRShadingNode
from rprblender import logging
import pyrprx


class RPR_Node_Output(RPRShadingNode):
    bl_compatibility = {'RPR'}
    bl_category = "Output"
    bl_class = "OUTPUT"
    bl_idname = 'rpr_shader_node_output'
    bl_label = 'RPR Material Output'
    bl_icon = 'MATERIAL'
    bl_width_min = 120

    def init(self, context):
        self.inputs.new("NodeSocketShader", "Surface")
        self.inputs.new("NodeSocketShader", "Volume")
        displacement = self.inputs.new("NodeSocketFloat", "Displacement")
        displacement.hide_value = True

    def sync(self, context):
        material = None
        logging.info("RPR_Node_Output inputs")
        for input in self.inputs:
            logging.info("[{}]: linked {}".format(input, input.is_linked))

        input = self.get_socket(self, name='Surface')
        if input and hasattr(input.node, 'sync'):
            logging.info("syncing {}".format(input.node))
            material = input.node.sync(context)

        return material
