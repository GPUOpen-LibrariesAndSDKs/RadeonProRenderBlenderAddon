import bpy
from .rpr_nodes import RPRShadingNode

import pyrprx


ShaderTypeUber2 = 0xFF


class RPR_Shader:
    handle: None

    def __init__(self, material):
        pass


class RPR_Node_Uber(RPRShadingNode):
    bl_category = "Shader"
    bl_class = "SHADER"
    bl_idname = 'rpr_shader_node_uber'
    bl_label = 'RPR Uber'
    bl_width_min = 300

    diffuse_color = 'Diffuse Color'
    diffuse_weight = 'Diffuse Weight'
    diffuse_roughness = 'Diffuse Roughness'
    diffuse_normal = 'Diffuse Normal'

    def diffuse_changed(self, context):
        self.inputs[self.diffuse_color].enabled = self.diffuse
        self.inputs[self.diffuse_roughness].enabled = self.diffuse

    def reflection_changed(self, context):
        pass

    diffuse: bpy.props.BoolProperty(name="Diffuse", update=diffuse_changed, default=True)
#    reflection: bpy.props.BoolProperty(name="Reflection", update=reflection_changed, default=True)

    def init(self, context):
        self.outputs.new("NodeSocketShader", "Output")

        self.inputs.new("rpr_socket_color", self.diffuse_color).default_value = (0.5, 0.5, 0.5, 1.0)
        self.inputs.new("rpr_socket_weight_soft", self.diffuse_weight).default_value = 1.0
        self.inputs.new("rpr_socket_weight", self.diffuse_roughness).default_value = 0.5

    def get_value(self, node, socket_name):
        return (0.5, 0.5, 0.5, 1.0)

    def sync(self, context):
        return None
        shader = UberShader2(self)
        if self.diffuse:
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_DIFFUSE_COLOR, (0.5, 0.5, 0.5, 1.0))
#                            self.get_value(blender_node, self..diffuse_color))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, (1.0, 1.0, 1.0, 1.0))
#                                  self.get_value(blender_node, self..diffuse_weight))
            shader.set_value_rprx(pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS, (0.5, 0.5, 0.5, 0.5))
#                                  self.get_value(blender_node, self.diffuse_roughness))
        return shader

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.alignment = 'EXPAND'

        col.prop(self, 'diffuse', toggle=True)
#        if self.diffuse:
#            col.prop(self, 'diffuse_use_shader_normal', toggle=False)
#            col.prop(self, 'backscatter_separate_color', toggle=False)
