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
from bpy.types import NodeSocket, NodeSocketInterface
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
)

from rprblender.utils import BLENDER_VERSION


COLORS = {
    'color': (0.78, 0.78, 0.16, 1.0),
    'gray': (0.78, 0.78, 0.78, 0.5),
    'float': (0.63, 0.63, 0.63, 1.0),
    'vector': (0.39, 0.39, 0.78, 1.0),
    'link': (0.78, 0.16, 0.78, 1.0),
}


# Blender 3.0 and upper requires NodeSocketInterface classes for correct draw in Material Properties panel
class RPRNodeSocketInterface(NodeSocketInterface):
    def draw(self, context, layout):
        pass

    def draw_color(self, context):
        pass


class RPRNodeSocket(NodeSocket):
    def update(self, context):
        if BLENDER_VERSION >= "3.1":
            self.node.socket_value_update(context)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name)

    def draw_color(self, context, node):
        return COLORS['float']


class RPRSocketColorInterface(RPRNodeSocketInterface):
    bl_socket_idname = 'rpr_socket_color'


class RPRSocketColor(RPRNodeSocket):
    bl_idname = 'rpr_socket_color'
    bl_label = "Color socket"

    default_value: FloatVectorProperty(name='Color', subtype='COLOR', min=0.0, soft_max=1.0,
                                       size=4, default=(1.0, 1.0, 1.0, 1.0), update=RPRNodeSocket.update)

    def draw_color(self, context, node):
        return COLORS['color']


class RPRSocketFloatInterface(RPRNodeSocketInterface):
    bl_socket_idname = 'rpr_socket_float'


class RPRSocketFloat(RPRNodeSocket):
    bl_idname = 'rpr_socket_float'
    bl_label = "Float socket"

    default_value: FloatProperty(name="Float", default=0.0,
                                 update=RPRNodeSocket.update)


class RPRSocketWeightInterface(RPRNodeSocketInterface):
    bl_socket_idname = 'rpr_socket_weight'


class RPRSocketWeight(RPRNodeSocket):
    bl_idname = 'rpr_socket_weight'
    bl_label = "Weight socket"

    default_value: FloatProperty(name="Weight", default=0.0, min=0.0, soft_max=1.0, subtype='FACTOR',
                                 update=RPRNodeSocket.update)


class RPRSocketMin1Max1Interface(RPRNodeSocketInterface):
    bl_socket_idname = 'rpr_socket_float_min1_max1'


class RPRSocketMin1Max1(RPRNodeSocket):
    bl_idname = 'rpr_socket_float_min1_max1'
    bl_label = "Min 1 Max 1 socket"

    default_value: FloatProperty(name="Float", default=0.0, min=-1.0, max=1.0, subtype='FACTOR',
                                 update=RPRNodeSocket.update)


class RPRSocketAngle360Interface(RPRNodeSocketInterface):
    bl_socket_idname = 'rpr_socket_angle360'


class RPRSocketAngle360(RPRNodeSocket):
    bl_idname = 'rpr_socket_angle360'
    bl_label = 'Angle360 socket'

    default_value: FloatProperty(name="Angle", soft_min=0.0, soft_max=1.0, default=0.0, subtype='ANGLE',
                                 update=RPRNodeSocket.update)


class RPRSocketLinkInterface(RPRNodeSocketInterface):
    bl_socket_idname = 'rpr_socket_link'


class RPRSocketLink(RPRNodeSocket):
    bl_idname = 'rpr_socket_link'
    bl_label = "Normal socket"

    default_value: FloatVectorProperty(name="Vector4", size=4,
                                       update=RPRNodeSocket.update)

    def draw(self, context, layout, node, text):
        layout.label(text=self.name)
    
    def draw_color(self, context, node):
        return COLORS['vector']


class RPRSocketIORInterface(RPRNodeSocketInterface):
    bl_socket_idname = 'rpr_socket_ior'


class RPRSocketIOR(RPRNodeSocket):
    bl_idname = 'rpr_socket_ior'
    bl_label = 'IOR socket'

    default_value: FloatProperty(name="IOR", min=0.0, soft_max=3.0, default=1.5, update=RPRNodeSocket.update)


class RPRSocket_Float_Min0_SoftMax10Interface(RPRNodeSocketInterface):
    bl_socket_idname = 'rpr_socket_float_min0_softmax10'


class RPRSocket_Float_Min0_SoftMax10(RPRNodeSocket):
    bl_idname = 'rpr_socket_float_min0_softmax10'
    bl_label = 'Float_Min0_SoftMax10 socket'

    default_value: FloatProperty(name="Float_Min0_SoftMax10", min=0.0, soft_max=10.0, subtype='FACTOR',
                                 update=RPRNodeSocket.update)


class RPRSocketWeightSoftInterface(RPRNodeSocketInterface):
    bl_socket_idname = 'rpr_socket_weight_soft'


class RPRSocketWeightSoft(RPRNodeSocket):
    bl_idname = 'rpr_socket_weight_soft'
    bl_label = "Weight socket soft"

    default_value: FloatProperty(name="Weight Soft", min=0.0, soft_max=1.0, default=0.5, subtype='FACTOR',
                                 update=RPRNodeSocket.update)


class RPRSocketValueInterface(RPRNodeSocketInterface):
    bl_socket_idname = 'rpr_socket_value'


class RPRSocketValue(RPRNodeSocket):
    """ Socket to represent value as a float/vector/color by display_type """
    bl_idname = 'rpr_socket_value'
    bl_label = 'RPR socket value'

    def value_to_vector4(self):
        if self.display_type == 'COLOR':
            return self.value_color
        if self.display_type == 'FLOAT':
            return (self.value_float, self.value_float, self.value_float, self.value_float)
        return self.value_vector4

    @staticmethod
    def is_vector4_equal(a, b):
        return list(a) == list(b)

    def clamp_color(self, color):
        r = min(1, max(0, color[0]))
        g = min(1, max(0, color[1]))
        b = min(1, max(0, color[2]))
        a = min(1, max(0, color[3]))
        return (r, g, b, a)

    def update_value(self, context):
        """ Update display value at input value change """
        if self.display_type == 'COLOR':
            self.value_color = self.clamp_color(self.default_value)
        elif self.display_type == 'FLOAT':
            self.value_float = self.default_value[0]
        else:
            self.value_vector4 = self.default_value[:]

    def update_default_value(self, context):
        """ Update other representations and default_value at currently displayed value change """
        val = self.value_to_vector4()
        self['default_value'] = val

        if self.display_type != 'VECTOR':
            self['value_vector4'] = self.default_value[:]
        if self.display_type != 'COLOR':
            self['value_color'] = self.clamp_color(self.default_value)
        if self.display_type != 'FLOAT':
            self['value_float'] = val[0]

    # socket display type, hidden in UI; value changed by material node that uses this socket type
    display_type: EnumProperty(
        name='Type',
        items=(
            ('COLOR', "Color", "Color"),
            ('FLOAT', "Float", "Float"),
            ('VECTOR', "Vector", "Vector")
        ),
        default='VECTOR'
    )

    # store values for different display types
    value_vector4: FloatVectorProperty(
        name="Vector4",
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        update=update_default_value
    )
    value_float: FloatProperty(
        name="Float",
        default=1.0,
        update=update_default_value)
    value_color: FloatVectorProperty(
        name='Color', description="Color",
        subtype='COLOR', min=0.0, max=1.0, size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        update=update_default_value
    )

    # store main/output value
    default_value: FloatVectorProperty(
        name="Vector4", size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        update=update_value
    )

    # show/hide vector value type edit boxes
    show: BoolProperty(
        name="Show/Hide",
        default=False,
        update=RPRNodeSocket.update
    )

    def draw(self, context, layout, node, text):
        """ Display different UI for color, vector and float display types """
        if self.is_linked or self.is_output:
            layout.label(text=self.name)
        else:
            if self.display_type == 'COLOR':
                layout.prop(self, 'value_color', text='')
                layout.label(text=self.name)
            elif self.display_type == 'FLOAT':
                layout.prop(self, 'value_float', text=self.name)
            else:
                col = layout.column()
                row = col.row()
                row.label(text=self.name)
                row.prop(self, 'show', text='', icon='TRIA_UP' if self.show else 'TRIA_DOWN')
                if self.show:
                    col.prop(self, 'value_vector4', text='')

    def draw_color(self, context, node):
        return COLORS.get(self.display_type.lower(), COLORS['float'])
