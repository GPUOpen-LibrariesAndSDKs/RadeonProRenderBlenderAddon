import bpy
import math
from . import rpraddon
from rprblender import logging

float_socket_color = (0.63, 0.63, 0.63, 1.0)

@rpraddon.register_class
class RPRSocketWeight(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_weight'
    bl_label = 'Weight socket'

    default_value = bpy.props.FloatProperty(name="Weight", min=0.0, max=1.0, default=0.5)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name, slider=True)

    def draw_color(self, context, node):
        return float_socket_color


@rpraddon.register_class
class RPRSocketScatteringDirection(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_scattering_direction'
    bl_label = 'Scattering Direction'

    default_value = bpy.props.FloatProperty(name="Scattering Direction", min=-1.0, max=1.0, default=0.0)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name, slider=True)

    def draw_color(self, context, node):
        return float_socket_color


@rpraddon.register_class
class RPRSocketIOR(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_ior'
    bl_label = 'IOR socket'

    default_value = bpy.props.FloatProperty(name="IOR", min=1.0, soft_max=10.0, default=1.0)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name, slider=True)

    def draw_color(self, context, node):
        return float_socket_color


@rpraddon.register_class
class RPRSocketAngle360(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_angle360'
    bl_label = 'Angle360 socket'

    default_value = bpy.props.FloatProperty(name="Angle", soft_min=-math.radians(360), soft_max=math.radians(360),
                                            default=0.0, subtype='ANGLE')

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name, slider=True)

    def draw_color(self, context, node):
        return float_socket_color


@rpraddon.register_class
class RPRSocketFactor(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_factor'
    bl_label = 'Factor socket'

    default_value = bpy.props.FloatProperty(
        name="Factor",
        default=1.0,
        min=0.0,
        step=0.1,
        precision=2
    )

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name)

    def draw_color(self, context, node):
        return float_socket_color


@rpraddon.register_class
class RPRSocketUV(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_uv'
    bl_label = 'UV socket'

    default_value = bpy.props.FloatVectorProperty(
        name="UV",
        default=(0.0, 0.0),
        size=2
    )

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name)

    def draw_color(self, context, node):
        return float_socket_color


@rpraddon.register_class
class RPRSocketColor(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_color'
    bl_label = 'Color socket'

    default_value = bpy.props.FloatVectorProperty(name='Color', subtype='COLOR', min=0.0, soft_max=1.0,
                                                  size=4, default=(1.0, 1.0, 1.0, 1.0))

    def draw(self, context, layout, node, text):
        if self.is_linked or self.is_output:
            layout.label(text=self.name)
        else:
            row = layout.row()
            row.alignment = 'LEFT'
            row.prop(self, 'default_value', text='')
            row.label(text)

    def draw_color(self, context, node):
        return float_socket_color


@rpraddon.register_class
class RPRSocketTransform(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_transform'
    bl_label = 'Transform socket'

    default_value = bpy.props.FloatVectorProperty(name='Mapping', size=4, default=(1.0, 1.0, 1.0, 1.0))

    def draw(self, context, layout, node, text):
        layout.label(text=self.name)

    def draw_color(self, context, node):
        return float_socket_color


@rpraddon.register_class
class RPRSocketVector4(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_vector4'
    bl_label = 'Vector4 socket'

    default_value = bpy.props.FloatVectorProperty(name="Vector4", size=4)

    def draw(self, context, layout, node, text):
        if self.is_linked or self.is_output:
            layout.label(text=self.name)
        else:
            col = layout.column()
            col.label(text=self.name)
            col.prop(self, 'default_value', text='')

    def draw_color(self, context, node):
        return float_socket_color


@rpraddon.register_class
class RPRSocketValue(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_value'
    bl_label = 'RPR socket value'

    def get_value_types():
        return (('color', "Color", "Color"),
                ('float', "Float", "Float"),
                ('vector', "Vector", "Vector"))

    def value_to_vector4(self):
        if self.type == 'color':
            return self.value_color
        elif self.type == 'float':
            return (self.value_float, self.value_float, self.value_float, self.value_float)
        else:
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
        if self.type == 'color':
            self.value_color = self.clamp_color(self.default_value)
        elif self.type == 'float':
            self.value_float = self.default_value[0]
        else:
            self.value_vector4 = self.default_value

    def update_default_value(self, context):
        val = self.value_to_vector4()
        self['default_value'] = val

        if self.type != 'vector':
            self['value_vector4'] = self.default_value
        if self.type != 'color':
            self['value_color'] = self.clamp_color(self.default_value)
        if self.type == 'float':
            self['value_float'] = self.default_value[0]

    type = bpy.props.EnumProperty(
        name='Type',
        items=get_value_types(),
        default='vector'
    )

    value_vector4 = bpy.props.FloatVectorProperty(name="Vector4", size=4, update=update_default_value)
    value_float = bpy.props.FloatProperty(name="Float", update=update_default_value)
    value_color = bpy.props.FloatVectorProperty(
        name='Color', description="Color",
        subtype='COLOR', min=0.0, max=1.0, size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        update=update_default_value
    )

    default_value = bpy.props.FloatVectorProperty(name="Vector4", size=4,
                                                default=(1.0, 1.0, 1.0, 1.0),
                                                update=update_value)

    show = bpy.props.BoolProperty(
        name="Show/Hide",
        default=False,
    )

    def draw(self, context, layout, node, text):
        if self.is_linked or self.is_output:
            layout.label(text=self.name)
        else:
            if self.type == 'color':
                layout.prop(self, 'value_color', text='')
                layout.label(self.name)
            elif self.type == 'float':
                layout.prop(self, 'value_float', text=self.name)
            else:
                col = layout.column()
                row = col.row()
                row.label(text=self.name)
                row.prop(self, 'show', text='', icon='TRIA_UP' if self.show else 'TRIA_DOWN')
                if self.show:
                    col.prop(self, 'value_vector4', text='')

    def draw_color(self, context, node):
        return float_socket_color


@rpraddon.register_class
class RPRSocketLink(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_link'
    bl_label = 'Link socket'

    default_value = bpy.props.FloatVectorProperty(name="Vector4", size=4)

    def draw(self, context, layout, node, text):
            layout.label(text=self.name)

    def draw_color(self, context, node):
        return float_socket_color


@rpraddon.register_class
class RPRSocketFloat(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_float'
    bl_label = 'Float socket'

    default_value = bpy.props.FloatProperty(name="Float", default=0.0)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name)

    def draw_color(self, context, node):
        return float_socket_color



#Sockets for Uber2
@rpraddon.register_class
class RPRSocketBoolean(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_boolean'
    bl_label = 'Boolean Socket'

    default_value = bpy.props.BoolProperty(name="Toggle",default=False)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name)

    def draw_color(self, context, node):
        return float_socket_color

@rpraddon.register_class
class RPRSocket_Float_SoftMin0_SoftMax1(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_float_softMin0_softMax1'
    bl_label = 'Float_SoftMin0_SoftMax1 socket'

    default_value = bpy.props.FloatProperty(name="Float_SoftMin0_SoftMax1", soft_min=0.0, soft_max=1.0)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name, slider=True)

    def draw_color(self, context, node):
        return float_socket_color

@rpraddon.register_class
class RPRSocket_Float_SoftMinN1_SoftMax1(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_float_softMinN1_softMax1'
    bl_label = 'Float_SoftMinN1_SoftMax1 socket'

    default_value = bpy.props.FloatProperty(name="Float_SoftMinN1_SoftMax1", soft_min=-1.0, soft_max=1.0)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name, slider=True)

    def draw_color(self, context, node):
        return float_socket_color

@rpraddon.register_class
class RPRSocket_Float_SoftMin0_SoftMax2(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_float_softMin0_softMax2'
    bl_label = 'Float_SoftMin0_SoftMax2 socket'

    default_value = bpy.props.FloatProperty(name="Float_SoftMin0_SoftMax2", soft_min=0.0, soft_max=2.0)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name, slider=True)

    def draw_color(self, context, node):
        return float_socket_color

@rpraddon.register_class
class RPRSocket_Float_SoftMin0_SoftMax10(bpy.types.NodeSocket):
    bl_idname = 'rpr_socket_float_softMin0_softMax10'
    bl_label = 'Float_SoftMin0_SoftMax10 socket'

    default_value = bpy.props.FloatProperty(name="Float_SoftMin0_SoftMax10", soft_min=0.0, soft_max=10.0)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=self.name)
        else:
            layout.prop(self, 'default_value', text=self.name, slider=True)

    def draw_color(self, context, node):
        return float_socket_color