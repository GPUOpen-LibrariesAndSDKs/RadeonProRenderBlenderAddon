import bpy

from .rpr_nodes import RPRShadingNode


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
        return None
