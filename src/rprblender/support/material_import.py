import ast
import io
import os
import xml.etree.ElementTree
from pathlib import Path

import pyrprapi
import shutil

import sys

try:
    from rprblender import logging


    def log(*args):
        logging.debug(*args, tag='material.import')
except:
    import logging


    def log(*args):
        logging.debug(' '.join(str(arg) for arg in args))


def get_float4_first_component(value):
    return ast.literal_eval(value)[0]


class BasicNodeCompiler:
    compiler = None  # type: Compiler
    node_instance = None

    def compile_input_node(self, name, value):
        return self.compiler.compile_node(self.compiler.nodes[value], self.depth + 1)

    def compile_input_value(self, name, value):
        return ast.literal_eval(value)

    def compile_input_special(self, name, value):
        """ in case input is not converted directly to blender socket input"""
        logging.warn('compile_input_special fails (name: %s, value: %s)' % (name, value))

    def get_input_socket(self, name):
        return None

    def load_image(self, path):
        return self.compiler.image_loader.load_image(path)


class NodeCompiler(BasicNodeCompiler):
    pass


class BasicMaterialNodeCompiler(NodeCompiler):
    def get_input_socket(self, name):
        return self.node_instance.get_input_socket_by_name(name)


class WardMaterialCompiler(BasicMaterialNodeCompiler):
    def compile_input_value(self, name, value):
        if 'rotation' == name:
            return get_float4_first_component(value)
        if name in {'roughness_x', 'roughness_y'}:
            return get_float4_first_component(value)
        return super().compile_input_value(name, value)


class MicrofacetMaterialCompiler(BasicMaterialNodeCompiler):
    def compile_input_value(self, name, value):
        logging.info('name: ', name)

        if name in {'roughness'}:
            return get_float4_first_component(value)
        return super().compile_input_value(name, value)


class MicrofacetRefractionMaterialCompiler(MicrofacetMaterialCompiler):
    def compile_input_value(self, name, value):
        if name in {'ior'}:
            return get_float4_first_component(value)
        return super().compile_input_value(name, value)


class OrenNayarMaterialCompiler(BasicMaterialNodeCompiler):
    def compile_input_value(self, name, value):
        if name in {'roughness'}:
            return get_float4_first_component(value)
        return super().compile_input_value(name, value)


class RefractonMaterialCompiler(BasicMaterialNodeCompiler):
    def compile_input_value(self, name, value):
        if name in {'ior'}:
            return get_float4_first_component(value)
        return super().compile_input_value(name, value)


class BlendMaterialCompiler(BasicMaterialNodeCompiler):
    def compile_input_value(self, name, value):
        if 'weight' == name:
            return get_float4_first_component(value)
        return super().compile_input_value(name, value)

    def get_input_socket(self, name):
        if name in ['color0', 'color1']:
            return self.node_instance.get_input_socket_by_name(
                {'color0': 'shader1', 'color1': 'shader2'}[name])
        return super().get_input_socket(name)


class MathNodeCompiler(NodeCompiler):
    socket_map = {'color0': 0, 'color1': 1}

    def compile_input_special(self, name, value):
        if 'op' == name:
            self.node_instance.op = self.compiler.op2name[self.compile_input_value(name, value)]
        else:
            self.node_instance.set_operand_value({'color0': 0, 'color1': 1}[name],
                                                 self.compile_input_value(name, value))

    def get_input_socket(self, name):
        if name in self.socket_map:
            return self.node_instance.get_input_operand_socket(self.socket_map[name])


class BumpmapNodeCompiler(NodeCompiler):
    def compile_input_value(self, name, value):
        if 'bumpscale' == name:
            return get_float4_first_component(value)
        return super().compile_input_value(name, value)

    def get_input_socket(self, name):
        if 'data' == name:
            return self.node_instance.get_input_socket_by_name('map')
        if 'uv' == name:
            return self.node_instance.get_input_socket_by_name('mapping')
        if 'bumpscale' == name:
            return None  # not allowing node input for scale
        if 'gamma' == name:
            return None
        return self.node_instance.get_input_socket_by_name(name)

    def compile_input_node(self, name, value):
        if 'data' == name:
            compiler = self.compiler
            fpath = compiler.nodes[value].find('param').get('value')

            image_node = compiler.editor.create_image_texture_node()
            image_node.set_image(self.load_image(fpath))
            return image_node
        return super().compile_input_node(name, value)

    def compile_input_special(self, name, value):
        if 'bumpscale' == name:
            self.node_instance.set_scale_value(self.compile_input_value(name, value))


class Noise2dNodeCompiler(NodeCompiler):
    def get_input_socket(self, name):
        if 'uv' == name:
            return self.node_instance.get_input_socket_by_name('mapping')
        return self.node_instance.get_input_socket_by_name(name)


class FresnelNodeCompiler(NodeCompiler):
    def compile_input_value(self, name, value):
        if 'ior' == name:
            return get_float4_first_component(value)
        return super().compile_input_value(name, value)

    def get_input_socket(self, name):
        if 'invec' == name:
            return self.node_instance.get_input_socket_by_name('in_vec')
        if 'n' == name:
            return self.node_instance.get_input_socket_by_name('normal')
        return self.node_instance.get_input_socket_by_name(name)


class FresnelSchlickNodeCompiler(NodeCompiler):
    def compile_input_value(self, name, value):
        if 'reflectance' == name:
            return get_float4_first_component(value)
        return super().compile_input_value(name, value)

    def get_input_socket(self, name):
        if 'invec' == name:
            return self.node_instance.get_input_socket_by_name('in_vec')
        return self.node_instance.get_input_socket_by_name(name)


class BlendValueNodeCompiler(BasicMaterialNodeCompiler):
    def compile_input_value(self, name, value):
        if 'weight' == name:
            return get_float4_first_component(value)
        return super().compile_input_value(name, value)

    def get_input_socket(self, name):
        if name in ['color0', 'color1']:
            return self.node_instance.get_input_socket_by_name(
                {'color0': 'value1', 'color1': 'value2'}[name])
        return super().get_input_socket(name)


NormalmapNodeCompiler = BumpmapNodeCompiler


class ImageTextureCompiler(NodeCompiler):
    def compile_input_special(self, name, value):
        # for image texture node just get it's input_texture's image(it's not a separate node for us in blender)
        if 'data' == name:
            input_texture_node = self.compiler.nodes[value]
            assert 'INPUT_TEXTURE' == input_texture_node.get('type')
            fpath = input_texture_node.find('param').get('value')
            self.node_instance.set_image(self.load_image(fpath))
            return
        assert 'gamma' == name

    def get_input_socket(self, name):
        if name in ['uv']:
            return self.node_instance.get_input_socket_by_name('mapping')
        return super().get_input_socket(name)


class LookupNodeCompiler(NodeCompiler):
    def compile_input_special(self, name, value):
        assert 'value' == name
        index = int(value)
        self.node_instance.set_type('UV N P INVEC OUTVEC'.split()[index])


class UnsupportedNode(Exception):
    def __init__(self, node_type):
        super().__init__("Unsupported node:", node_type)
        self.node_type = node_type


class Compiler:
    def __init__(self, nodes, material_editor, image_loader):
        self.nodes = nodes
        self.compiled_nodes = {}
        self.editor = material_editor

        self.image_loader = image_loader

        api_desc_fpath = str(Path(pyrprapi.__file__).parent / 'pyrprapi.json')
        self.api = pyrprapi.load(api_desc_fpath)

        op_prefix = 'RPR_MATERIAL_NODE_OP_'

        self.op2name = {ast.literal_eval(self.api.constants[name].value): name.replace(op_prefix, '')
                        for name in self.api.constants
                        if op_prefix in name}

    def get_node_compiler(self, node_type):
        node_compilers = {
            'EMISSIVE': (self.editor.create_emissive_material_node, BasicMaterialNodeCompiler),
            'WARD': (self.editor.create_ward_material_node, WardMaterialCompiler),
            'DIFFUSE': (self.editor.create_diffuse_material_node, BasicMaterialNodeCompiler),
            'MICROFACET': (self.editor.create_microfacet_material_node, MicrofacetMaterialCompiler),
            'MICROFACET_REFRACTION': (self.editor.create_microfacet_refraction_material_node,
                                      MicrofacetRefractionMaterialCompiler),
            'REFLECTION': (self.editor.create_reflection_material_node, BasicMaterialNodeCompiler),
            'REFRACTION': (self.editor.create_refraction_material_node, RefractonMaterialCompiler),
            'BLEND': (self.editor.create_blend_material_node, BlendMaterialCompiler),
            'TRANSPARENT': (self.editor.create_transparent_material_node, BasicMaterialNodeCompiler),
            'ORENNAYAR': (self.editor.create_oren_nayar_material_node, OrenNayarMaterialCompiler),
            'IMAGE_TEXTURE': (self.editor.create_image_texture_node, ImageTextureCompiler),
            'BUMP_MAP': (self.editor.create_bumpmap_node, BumpmapNodeCompiler),
            'NORMAL_MAP': (self.editor.create_normalmap_node, NormalmapNodeCompiler),
            'INPUT_LOOKUP': (self.editor.create_input_lookup_node, LookupNodeCompiler),
            'ARITHMETIC': (self.editor.create_math_node, MathNodeCompiler),
            'BLEND_VALUE': (self.editor.create_blend_value_node, BlendValueNodeCompiler),
            'NOISE2D_TEXTURE': (self.editor.create_noise2d_node, Noise2dNodeCompiler),
            'FRESNEL': (self.editor.create_fresnel_node, FresnelNodeCompiler),
            'FRESNEL_SCHLICK': (self.editor.create_fresnel_schlick_node, FresnelSchlickNodeCompiler),
        }

        if node_type not in node_compilers:
            raise UnsupportedNode(node_type)

        return node_compilers[node_type]

    def compile(self, root_node):
        return self.compile_node(root_node)

    def compile_node(self, node, depth=0):
        if node in self.compiled_nodes:
            return self.compiled_nodes[node]
        log('  ' * depth, node.get('name'), node.get('type'))

        node_compiler, node_instance = self.create_compiler_for_node(node, depth)

        log(node.get('name'), node.get('type'))
        for param in node.iter(tag='param'):
            param_type = param.get('type')
            param_name = param.get('name')
            param_value = param.get('value')
            log('  ' * depth, 'param', param_name, param_type)

            input_socket = node_compiler.get_input_socket(param_name)

            if input_socket:
                if 'connection' == param_type:
                    self.editor.link_nodes(
                        node_compiler.compile_input_node(param_name, param_value),
                        input_socket)
                else:
                    node_instance.set_input_socket_value(
                        input_socket, node_compiler.compile_input_value(param_name, param_value))
            else:
                node_compiler.compile_input_special(param_name, param_value)
        self.compiled_nodes[node] = node_instance
        return node_instance

    def create_compiler_for_node(self, node, depth):
        node_type = node.get('type')
        create_node_instance, create_node_compiler = self.get_node_compiler(node_type)
        node_instance = create_node_instance()
        node_compiler = create_node_compiler()
        node_compiler.compiler = self
        node_compiler.node_instance = node_instance
        node_compiler.depth = depth
        return node_compiler, node_instance


class MaterialImageLoader:
    def __init__(self, load_image, root_folder, material_folder, copy_image=None):
        self.root_folder = root_folder
        self.material_folder = material_folder
        self._copy_image = copy_image
        self._load_image = load_image

    def load_image(self, fpath):
        if self._copy_image is None:
            if '\\' in fpath:
                fpath_full = self.root_folder + '/' + fpath
            else:
                fpath_full = self.material_folder + '/' + fpath
            return self._load_image(fpath_full)
        else:
            if '\\' in fpath:
                fpath_full = self.root_folder + '/' + fpath
                fpath_relative = fpath
            else:
                fpath_full = self.material_folder + '/' + fpath
                fpath_relative = os.path.basename(self.material_folder) + '/' + fpath

            return self._load_image(self._copy_image(fpath_full, 'rprmaterials' + '/' + fpath_relative))


def iter_materials(root):
    for material in root.iter(tag='material'):
        material_name = material.get('name')
        yield material_name, {node.get('name'): node for node in material.iter(tag='node')}


def compile_material_from_xml(material_xml, material_editor, image_loader):
    tree = xml.etree.ElementTree.parse(io.StringIO(material_xml))
    for material_name, nodes in iter_materials(tree.getroot()):
        return Compiler(nodes, material_editor, image_loader).compile(nodes[material_name])
