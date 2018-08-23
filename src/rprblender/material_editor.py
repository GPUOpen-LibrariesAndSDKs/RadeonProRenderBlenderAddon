import bpy

from rprblender import logging


class Node:
    def __init__(self, node, editor):
        self.node = node
        self.editor = editor

    def get_input_socket_by_name(self, name):
        attr_name = name + '_in'
        if not hasattr(self.node, attr_name):
            return None
        return self.node.inputs[getattr(self.node, attr_name)]

    def set_input_socket_value_by_name(self, name, value):
        self.get_input_socket_by_name(name).default_value = value

    def set_input_socket_value(self, socket, value):
        socket.default_value = value

    # new
    def get_input_socket(self, socket_name):
        return self.node.inputs[socket_name]

    def link_to(self, input_socket):
        self.editor.tree.links.new(self.get_output_socket(), input_socket)


class ValueNode(Node):
    def get_output_socket(self):
        return self.node.outputs[self.node.value_out]


class RampNode(Node):
    def get_output_socket(self):
        return self.node.outputs['Color']


class OutputNode(Node):
    def get_input_shader_socket(self):
        return self.get_input_socket_by_name('shader')

    def get_input_volume_socket(self):
        return self.get_input_socket_by_name('volume')


class Material(Node):
    def set_color_value(self, value):
        self.set_input_socket_value_by_name('color', value)

    def get_output_socket(self):
        return self.node.outputs[self.node.shader_out]

    def get_input_color_socket(self):
        return self.get_input_socket_by_name('color')


class EmissiveMaterial(Material):
    pass


class DiffuseMaterial(Material):
    def get_input_normal_socket(self):
        return self.get_input_socket_by_name('normal')


class WardMaterial(Material):
    def get_input_roughness_y_socket(self):
        return self.get_input_socket_by_name('roughness_y')

    def get_input_roughness_x_socket(self):
        return self.get_input_socket_by_name('roughness_x')

    def get_input_rotation_socket(self):
        return self.get_input_socket_by_name('rotation')


from . import versions

class ImageTexture(ValueNode):
    def set_image(self, image):
        if versions.is_blender_support_new_image_node():
            self.node.image = image
        else:
            self.node.image_name = image.name


class Lookup(ValueNode):
    def set_type(self, type):
        self.node.type = type


class MathNode(ValueNode):
    def _set_op(self, op):
        self.node.op = op

    op = property(fset=_set_op)

    def set_operand_value(self, i, value):
        self.node.inputs[i].default_value = value

    def get_input_operand_socket(self, i):
        return self.node.inputs[i]


class Bumpmap(ValueNode):
    def set_scale_value(self, value):
        self.node.inputs[self.node.scale_in].default_value = value

    def get_input_map_socket(self):
        return self.get_input_socket_by_name('map')

    def get_input_mapping_socket(self):
        return self.get_input_socket_by_name('mapping')


Normalmap = Bumpmap


class MaterialEditor:
    def __init__(self, tree):
        self.tree = tree

    def create_output_node(self):
        return OutputNode(self.tree.nodes.new(type='rpr_shader_node_output'), self)

    def create_emissive_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_emissive'), self)

    def create_diffuse_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_diffuse'), self)

    def create_ward_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_ward'), self)

    def create_microfacet_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_microfacet'), self)

    def create_uber_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_uber'), self)

    def create_uber_material_node2(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_uber2'), self)

    def create_uber_material_node3(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_uber3'), self)

    def create_pbr_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_pbr'), self)

    def create_pbr_material_node3(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_pbr3'), self)

    def create_reflection_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_reflection'), self)

    def create_refraction_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_refraction'), self)

    def create_blend_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_blend'), self)

    def create_volume_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_volume'), self)

    def create_subsurface_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_subsurface'), self)

    def create_transparent_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_transparent'), self)

    def create_microfacet_refraction_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_microfacet_refraction'), self)

    def create_diffuse_refraction_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_diffuse_refraction'), self)

    def create_oren_nayar_material_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_oren_nayar'), self)

    def create_input_lookup_node(self):
        return Lookup(self.tree.nodes.new(type='rpr_input_node_lookup'), self)

    def create_image_texture_node(self):
        return ImageTexture(self.tree.nodes.new(type='rpr_texture_node_image_map'), self)

    def create_bumpmap_node(self):
        return Bumpmap(self.tree.nodes.new(type='rpr_input_node_bumpmap'), self)

    def create_normalmap_node(self):
        return Normalmap(self.tree.nodes.new(type='rpr_input_node_normalmap'), self)

    def create_math_node(self):
        return MathNode(self.tree.nodes.new(type='rpr_arithmetics_node_math'), self)

    def create_blend_value_node(self):
        return ValueNode(self.tree.nodes.new(type='rpr_arithmetics_node_value_blend'), self)

    def create_value_node(self):
        return ValueNode(self.tree.nodes.new(type='rpr_input_node_value'), self)

    def create_noise2d_node(self):
        return ValueNode(self.tree.nodes.new(type='rpr_texture_node_noise2d'), self)

    def create_checker_node(self):
        return ValueNode(self.tree.nodes.new(type='rpr_texture_node_checker'), self)

    def create_fresnel_schlick_node(self):
        return ValueNode(self.tree.nodes.new(type='rpr_fresnel_schlick_node'), self)

    def create_fresnel_node(self):
        return ValueNode(self.tree.nodes.new(type='rpr_fresnel_node'), self)

    def create_fresnel_color_blend_node(self):
        return ValueNode(self.tree.nodes.new(type='rpr_fresnel_color_blend_node'), self)

    def create_input_constant_node(self):
        return ValueNode(self.tree.nodes.new(type='rpr_input_node_constant'), self)

    def create_input_value_node(self):
        return ValueNode(self.tree.nodes.new(type='rpr_input_node_value'), self)

    def create_displacement_node(self):
        return Material(self.tree.nodes.new(type='rpr_shader_node_displacement'), self)

    def create_mapping_node(self):
        return MathNode(self.tree.nodes.new(type='rpr_mapping_node'), self)

    def create_ramp_node(self):
        return RampNode(self.tree.nodes.new(type='ShaderNodeValToRGB'), self)

    def link_nodes(self, output, input_socket):
        if not output or not input_socket:
            return
        logging.debug("linknodes: %s to %s" % (output, input_socket), tag='material')
        self.tree.links.new(output.get_output_socket(), input_socket)

    def load_image(self, fpath):
        logging.debug("load_image:", fpath, tag='material')
        image = bpy.data.images.load(fpath)
        return image
