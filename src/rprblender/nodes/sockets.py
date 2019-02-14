from bpy.types import NodeSocket
from bpy.props import (
    FloatProperty,
    FloatVectorProperty,
)
import math


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


class RPRSocketMin1Max1(NodeSocket):
    bl_idname = 'rpr_socket_float_min1_max1'
    bl_label = "Min 1 Max 1 socket"

    default_value: FloatProperty(name="Float", default=0.0, min=-1.0, max=1.0)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name)

    def draw_color(self, context, node):
        return COLORS['gray']


class RPRSocketAngle360(NodeSocket):
    bl_idname = 'rpr_socket_angle360'
    bl_label = 'Angle360 socket'

    default_value: FloatProperty(name="Angle", soft_min=-math.radians(180), soft_max=math.radians(180),
                                            default=0.0, subtype='ANGLE')

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name, slider=True)

    def draw_color(self, context, node):
        return COLORS['float']


class RPRSocketLink(NodeSocket):
    bl_idname = 'rpr_socket_link'
    bl_label = "Normal socket"

    default_value: FloatVectorProperty(name="Vector4", size=4)

    def draw(self, context, layout, node, text):
        layout.label(text=self.name)
    
    def draw_color(self, context, node):
        return COLORS['normal']


class RPRSocketIOR(NodeSocket):
    bl_idname = 'rpr_socket_ior'
    bl_label = 'IOR socket'

    default_value: FloatProperty(name="IOR", min=0.0, soft_max=3.0, default=1.5)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name, slider=True)

    def draw_color(self, context, node):
        return COLORS['float']


class RPRSocket_Float_Min0_SoftMax10(NodeSocket):
    bl_idname = 'rpr_socket_float_min0_softmax10'
    bl_label = 'Float_Min0_SoftMax10 socket'

    default_value: FloatProperty(name="Float_Min0_SoftMax10", min=0.0, soft_max=10.0)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name, slider=True)

    def draw_color(self, context, node):
        return COLORS['float']


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


classes = (RPRSocketColor, RPRSocketFloat, RPRSocketWeight, RPRSocketWeightSoft,
           RPRSocketMin1Max1, RPRSocketLink, RPRSocketIOR, RPRSocket_Float_Min0_SoftMax10,
           RPRSocketAngle360)
