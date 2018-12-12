from bpy.types import NodeSocket
from bpy.props import (
    FloatProperty,
    FloatVectorProperty,
)


COLORS = {
    'color': (0.78, 0.78, 0.16, 1.0),
    'gray': (0.78, 0.78, 0.78, 0.5),
    'float': (0.63, 0.63, 0.63, 1.0),
    'normal': (0.78, 0.16, 0.78, 1.0),
    'link': (0.78, 0.16, 0.78, 1.0),
}


class RPRSocketColor(NodeSocket):
    bl_idname = 'rpr_socket_color'
    bl_label = "Color socket"

    default_value: FloatVectorProperty(name='Color', subtype='COLOR', min=0.0, soft_max=1.0,
                                                  size=4, default=(1.0, 1.0, 1.0, 1.0))

    def draw(self, context, layout, node, text):
        if self.is_linked or self.is_output:
            layout.label(text=self.name)
        else:
            row = layout.row()
            row.alignment = 'LEFT'
            row.prop(self, 'default_value', text='')
            row.label(text=text)

    def draw_color(self, context, node):
        return COLORS['link']


class RPRSocketFloat(NodeSocket):
    bl_idname = 'rpr_socket_float'
    bl_label = "Float socket"

    default_value: FloatProperty(name="Float", default=0.0)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name)

    def draw_color(self, context, node):
        return COLORS['gray']


class RPRSocketWeight(NodeSocket):
    bl_idname = 'rpr_socket_weight'
    bl_label = "Weight socket"

    default_value: FloatProperty(name="Weight", default=0.0)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name)

    def draw_color(self, context, node):
        return COLORS['gray']


class RPRSocketWeightSoft(NodeSocket):
    bl_idname = 'rpr_socket_weight_soft'
    bl_label = "Weight socket soft"

    default_value: FloatProperty(name="Weight Soft", min=0.0, soft_max=1.0, default=0.5)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name)

    def draw_color(self, context, node):
        return COLORS['gray']


classes = (RPRSocketColor, RPRSocketFloat, RPRSocketWeight, RPRSocketWeightSoft)
