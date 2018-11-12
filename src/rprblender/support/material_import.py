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


def get_float4_as_float2(value):
    return ast.literal_eval(value)[0:2]


def get_float4_as_float3(value):
    return ast.literal_eval(value)[0:3]


class BasicNodeCompiler:
    depth = None
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

    def set_socket_value(self, input_socket, value):
        self.node_instance.set_input_socket_value(input_socket, value)

    # "Virtual" method
    def update_node(self):
        """
        Post-import update
        """
        pass


class NodeCompiler(BasicNodeCompiler):
    pass


class BasicMaterialNodeCompiler(NodeCompiler):
    def get_input_socket(self, name):
        return self.node_instance.get_input_socket_by_name(name)


class Uber3MaterialCompiler(BasicMaterialNodeCompiler):
    class Uber3SocketInfo:
        def __init__(self, name, type_name, socket_to_update=''):
            self.name = name
            self.type_name = type_name
            self.socket_to_update = socket_to_update

    input_sockets_info = {'diffuse.color': Uber3SocketInfo('Diffuse Color', 'float4', 'diffuse'),
                          'diffuse.weight': Uber3SocketInfo('Diffuse Weight', 'float', 'diffuse'),
                          'diffuse.roughness': Uber3SocketInfo('Diffuse Roughness', 'float', 'diffuse'),
                          'reflection.color': Uber3SocketInfo('Reflection Color', 'float4', 'reflection'),
                          'reflection.weight': Uber3SocketInfo('Reflection Weight', 'float', 'reflection'),
                          'reflection.roughness': Uber3SocketInfo('Reflection Roughness', 'float', 'reflection'),
                          'reflection.anisotropy': Uber3SocketInfo('Reflection Anisotropy', 'float', 'reflection'),
                          'reflection.anistropyRotation': Uber3SocketInfo('Reflection Anisotropy Rotation', 'float', 'reflection'),
                          'reflection.ior': Uber3SocketInfo('Reflection IOR', 'float', 'reflection'),
                          'refraction.color': Uber3SocketInfo('Refraction Color', 'float4', 'refraction'),
                          'refraction.weight': Uber3SocketInfo('Refraction Weight', 'float', 'refraction'),
                          'refraction.roughness': Uber3SocketInfo('Refraction Roughness', 'float', 'refraction'),
                          'refraction.ior': Uber3SocketInfo('Refraction IOR', 'float', 'refraction'),
                          'refraction.absorptionColor': Uber3SocketInfo('Refraction Absorption Color', 'float4', 'refraction'),
                          'refraction.absorptionDistance': Uber3SocketInfo('Refraction Absorption Distance', 'float', 'refraction'),
                          'coating.color': Uber3SocketInfo('Coating Color', 'float4', 'coating'),
                          'coating.weight': Uber3SocketInfo('Coating Weight', 'float', 'coating'),
                          'coating.roughness': Uber3SocketInfo('Coating Roughness', 'float', 'coating'),
                          'coating.ior': Uber3SocketInfo('Coating IOR', 'float', 'coating'),
                          'coating.metalness': Uber3SocketInfo(None, 'float', 'coating'),           # unused
                          'coating.transmissionColor': Uber3SocketInfo('Coating Transmission Color', 'float4', 'coating'),
                          'coating.thickness': Uber3SocketInfo('Coating Thickness', 'float', 'coating'),
                          'sheen.weight': Uber3SocketInfo('Sheen Weight', 'float', 'sheen'),
                          'sheen': Uber3SocketInfo('Sheen Color', 'float4', 'sheen'),
                          'sheen.tint': Uber3SocketInfo('Sheen Tint', 'float', 'sheen'),
                          'emission.color': Uber3SocketInfo('Emissive Color', 'float4', 'emission'),
                          'emission.weight': Uber3SocketInfo('Emissive Weight', 'float', 'emission'),
                          'transparency': Uber3SocketInfo('Transparency', 'float'),
                          'sss.scatterColor': Uber3SocketInfo('Subsurface Scattering Color', 'float4'),
                          'sss.scatterDistance': Uber3SocketInfo('Subsurface Radius', 'float3'),
                          'sss.scatterDirection': Uber3SocketInfo('Subsurface Scattering Direction', 'float'),
                          'sss.weight': Uber3SocketInfo('Subsurface Weight', 'float'),
                          'backscatter.weight': Uber3SocketInfo('Backscattering Weight', 'float'),
                          'backscatter.color': Uber3SocketInfo('Backscattering Color', 'float4'),

                          # inputs that should be linked only
                          'diffuse.normal': Uber3SocketInfo('Diffuse Normal', '', 'diffuse'), 
                          'reflection.normal': Uber3SocketInfo('Reflection Normal', '', 'reflection'), 
                          'refraction.normal': Uber3SocketInfo('Refraction Normal', '', 'refraction'),
                          'coating.normal': Uber3SocketInfo('Coating Normal', '', 'coating'),
                          'normal': Uber3SocketInfo('Normal', '', 'normal'),  
                          'displacement': Uber3SocketInfo('Displacement Map', '', 'displacement'),  

                          # additional internal input
                          'reflection.metalness': Uber3SocketInfo('Reflection Metalness', 'float'),
                          }

    ui_fields = {
        # MatLib values that are not inputs
        'reflection.mode': Uber3SocketInfo('reflection_mode', 'str'),
        'refraction.thinSurface': Uber3SocketInfo('refraction_thin_surface', 'bool'),
        'refraction.caustics': Uber3SocketInfo('refraction_caustics', 'bool'),
        'coating.mode': Uber3SocketInfo(None, 'str'),  # unused
        'emission.mode': Uber3SocketInfo('emissive_double_sided', 'bool'),
        'sss.multiscatter': Uber3SocketInfo('subsurface_multiple_scattering', 'bool'),

        # internal
        'sss.use.diffuse.color': Uber3SocketInfo('subsurface_use_diffuse_color', 'bool'),
        'backscatter.separate.color': Uber3SocketInfo('backscatter_separate_color', 'bool'),

        # weight and links
        'diffuse.weight': Uber3SocketInfo('diffuse', 'bool'),
        'reflection.weight': Uber3SocketInfo('reflection', 'bool'),
        'refraction.weight': Uber3SocketInfo('refraction', 'bool'),
        'coating.weight': Uber3SocketInfo('coating', 'bool'),
        'sheen.weight': Uber3SocketInfo('sheen', 'bool'),
        'emission.weight': Uber3SocketInfo('emissive', 'bool'),
        'sss.weight': Uber3SocketInfo('subsurface', 'bool'),
        'normal': Uber3SocketInfo('normal', 'bool'),
        'transparency': Uber3SocketInfo('transparency', 'bool'),
        'displacement': Uber3SocketInfo('displacement', 'bool'),

        # normals
        'diffuse.normal': Uber3SocketInfo('diffuse_use_shader_normal', 'bool'),
        'reflection.normal': Uber3SocketInfo('reflection_use_shader_normal', 'bool'),
        'refraction.normal': Uber3SocketInfo('refraction_use_shader_normal', 'bool'),
        'coating.normal': Uber3SocketInfo('coating_use_shader_normal', 'int'),
    }

    sections_to_update = ('diffuse.weight', 'reflection.weight', 'refraction.weight', 'coating.weight', 'sss.weight',
                          'sheen.weight', 'emission.weight',)

    ui_values_for_import = ('reflection.mode', 'refraction.thinSurface', 'refraction.caustics', 'coating.mode',
                            'emission.mode', 'sss.multiscatter')

    def get_input_socket(self, name):
        if name == 'reflection.ior':
            mode = self.get_ui_socket_value('reflection.mode')
            if mode is not None and mode == "METALNESS":
                name = 'reflection.metalness'
        elif name == 'coating.ior':
            mode = self.get_ui_socket_value('coating.mode')
            if mode is not None and mode == "METALNESS":
                name = 'coating.metalness'

        socket_info = self.input_sockets_info.get(name)
        if socket_info is None or socket_info.name is None:
            return None
        return self.node_instance.get_input_socket(socket_info.name)

    def get_ui_socket_value(self, name):
        socket_info = self.ui_fields.get(name)
        if socket_info is None or socket_info.name is None:
            return None
        return getattr(self.node_instance.node, socket_info.name)

    def set_ui_socket_value(self, name, value):
        socket_info = self.ui_fields.get(name)
        if socket_info is None or socket_info.name is None:
            return
        if name in ('reflection.mode', 'coating.mode'):
            value = {'1': 'IOR', '2': 'METALNESS'}[value]
        elif socket_info.type_name == 'bool':
            value = bool(int(value))

        setattr(self.node_instance.node, socket_info.name, value)

    def get_update_socket_info(self, name):
        socket_info = self.ui_fields.get(name)
        if socket_info is None or socket_info.name is None:
            return None
        return socket_info

    def compile_input_node(self, name, value):
        socket_info = self.input_sockets_info.get(name)
        if socket_info is None or socket_info.name is None:
            return None

        # set False for "use shader normal map" if normal map is linked to the section
        if name in ('diffuse.normal', 'reflection.normal', 'refraction.normal', 'coating.normal'):
            self.set_ui_socket_value(name, False)

        # enable sections for linked nodes only
        elif name in ('normal', 'transparency', 'displacement'):
            self.set_ui_socket_value(name, True)

            if name == 'displacement':  # prevent excessive mesh distortion
                self.node_instance.node.displacement_max = 0.025

        # use separate backscatter color if any link attached to it
        if name == 'backscatter.color':
            self.set_ui_socket_value('backscatter.separate.color', True)

        node = self.compiler.nodes[value]
        compiled_node = self.compiler.compile_node(node, self.depth + 1)
        return compiled_node

    def compile_input_value(self, name, value):
        socket_info = self.input_sockets_info.get(name)
        if socket_info is None or socket_info.name is None:
            return None
        if socket_info.type_name == "float3":
            return get_float4_as_float3(value)
        if socket_info.type_name == "float":
            return get_float4_first_component(value)
        if socket_info.type_name == "int":
            return int(get_float4_first_component(value))
        if socket_info.type_name == "bool":
            return bool(get_float4_first_component(value))
        return super().compile_input_value(name, value)

    def compile_input_special(self, name, value):
        if name in self.ui_values_for_import and self.get_ui_socket_value(name) is not None:
            return self.set_ui_socket_value(name, value)
        return super().compile_input_special(name, value)
    
    def set_socket_value(self, input_socket, value):
        # Coating Transmission Color passed as inverted, convert it back
        if input_socket.name == self.input_sockets_info["coating.transmissionColor"].name:
            value = (1.0 - value[0], 1.0 - value[1], 1.0 - value[2], 1.0)
        super(Uber3MaterialCompiler, self).set_socket_value(input_socket, value)

    def update_node(self):
        for input_socket_name in self.sections_to_update:
            socket_info = self.get_update_socket_info(input_socket_name)
            weight_socket = self.get_input_socket(input_socket_name)
            if weight_socket is not None:
                enabled = weight_socket.default_value > 0
                self.set_ui_socket_value(input_socket_name, enabled)

        # check for "Separate Backscatter Color": compare "diffuse.color" and "backscatter.color"
        diffuse_color = self.get_input_socket("diffuse.color").default_value
        backscatter_color = self.get_input_socket("backscatter.color").default_value
        not_equal = sum([1 for i in range(0, 4) if not diffuse_color[i] == backscatter_color[i]]) > 0
        if not_equal:
            info = self.get_update_socket_info('backscatter.separate.color')
            if info is not None:
                self.set_ui_socket_value(info.name, True)

        # check for "Subsurface Use Diffuse Color": compare "diffuse.color" and "Subsurface Scattering Color"
        subsurface_color = self.get_input_socket("sss.scatterColor").default_value
        not_equal = sum([1 for i in range(0, 4) if not diffuse_color[i] == subsurface_color[i]]) > 0
        if not_equal:
            info = self.get_update_socket_info('sss.use.diffuse.color')
            if info is not None:
                self.set_ui_socket_value(info.name, True)

        # total update of material node
        post_update_func = getattr(self.node_instance.node, 'total_update')
        post_update_func()


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
    socket_type = 'color'

    def compile_input_special(self, name, value):
        if 'op' == name:
            self.node_instance.op = self.compiler.op2name[self.compile_input_value(name, value)]
        else:
            compiled_value = self.compile_input_value(name, value)

            self.node_instance.set_operand_value({'color0': 0, 'color1': 1}[name], compiled_value)

    def get_input_socket(self, name):
        if name in self.socket_map:
            return self.node_instance.get_input_operand_socket(self.socket_map[name])

    def set_socket_value(self, input_socket, value):
        """Update input sockets type to hold values outside of "color" values area of [0.0..1.0]"""
        if isinstance(value, tuple) and self.socket_type in ('color', 'float'):
            out_of_color_range = sum([0 if 0.0 <= v <= 1.0 else 1 for v in value]) > 0
            equal = len(value) == 1 or sum([0 if v == value[0] else 1 for v in value[1:]]) == 0
            if out_of_color_range:
                if equal:
                    self.socket_type = 'float'
                else:
                    self.socket_type = 'vector'
                self.node_instance.set_operands_type(self.socket_type)
        elif isinstance(value, float) and self.socket_type == 'color':
            self.socket_type = 'float'
            self.node_instance.set_operands_type('float')

        super(MathNodeCompiler, self).set_socket_value(input_socket, value)


class BumpmapNodeCompiler(NodeCompiler):
    def compile_input_value(self, name, value):
        if name in ("scale", "bumpscale"):
            return get_float4_first_component(value)
        return super().compile_input_value(name, value)

    def get_input_socket(self, name):
        if name == 'color':
            name = 'data'
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
            return self.node_instance.set_scale_value(self.compile_input_value('scale', value))
        return super().compile_input_special(name, value)


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
    def compile_input_node(self, name, value):
        return self.compiler.compile_node(self.compiler.nodes[value], self.depth + 1, ignore_uv_lookup_node=True)

    def compile_input_special(self, name, value):
        # for image texture node just get it's input_texture's image(it's not a separate node for us in blender)
        if 'data' == name:
            input_texture_node = self.compiler.nodes[value]
            assert 'INPUT_TEXTURE' == input_texture_node.get('type')

            attach_mapping_node = False
            tiling_u = 1
            tiling_v = 1

            # image data in xml are linked as an INPUT_TEXTURE node, parse it
            for param in input_texture_node.iter(tag='param'):
                param_type = param.get('type')
                param_name = param.get('name')
                param_value = param.get('value')
                log('\tImageTexture ', 'param', param_name, param_type)

                if param_name == 'path':
                    self.node_instance.set_image(self.load_image(param_value))
                elif param_name == 'gamma':
                    self.node_instance.node.color_space_type = 'sRGB' if float(param_value) > 1.0 else 'Linear'

                # did we have the texture tiling info as well?
                if param_name in ("tiling_u", "tiling_v"):
                    attach_mapping_node = True
                    if param_name == "tiling_u":
                        tiling_u = float(param_value)
                    elif param_name == "tiling_v":
                        tiling_v = float(param_value)

            # tiling/offset texture info in Blender stored in a separate node, create and link it
            if attach_mapping_node:
                mapping_socket = self.get_input_socket("uv")
                fake_mapping_node_name = "fakeNodeMapping{}x{}".format(tiling_u, tiling_v)
                fake_mapping_node = self.compiler.getFakeXMLNode(fake_mapping_node_name)
                if not fake_mapping_node:
                    fake_mapping_node = FakeMappingXMLNode(fake_mapping_node_name, tiling_u, tiling_v)
                self.compiler.link_node(mapping_socket, self.compiler.compile_node(fake_mapping_node, self.depth+1))

    def get_input_socket(self, name):
        if name in ['uv']:
            return self.node_instance.get_input_socket_by_name('mapping')
        return super().get_input_socket(name)


class MappingNodeCompiler(BasicMaterialNodeCompiler):
    def compile_input_value(self, name, value):
        if name == "scale":
            if isinstance(value, tuple):
                return value
            return get_float4_as_float2(value)
        return super().compile_input_value(name, value)

class LookupNodeCompiler(NodeCompiler):
    def compile_input_special(self, name, value):
        assert 'value' == name
        index = int(value)
        self.node_instance.set_type('UV N P INVEC OUTVEC'.split()[index])


class UnsupportedNode(Exception):
    def __init__(self, node_type):
        super().__init__("Unsupported node:", node_type)
        self.node_type = node_type


class FakeMappingXMLNode(object):
    """Fake XML node to represent required Mapping node and allow it to be used in parsed nodes cache."""
    def __init__(self, name, tiling_u, tiling_v):
        self.tiling_u = tiling_u
        self.tiling_v = tiling_v
        self.name = name

    def iter(self, tag):
        """Return desired values for fake input socket"""
        return ({"name": "scale",
                 "type": "float2",
                 "value": (self.tiling_u, self.tiling_v),
                 },)

    def get(self, name):
        """Return basic node info"""
        if name == "name":
            return self.name
        if name == "type":
            return "MAPPING"
        raise AttributeError("FakeMappingXMLNode doesn't have representation of '{}' value!".format(name))


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

        self.fakeXMLNodes = {}

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
            'UBER': (self.editor.create_uber_material_node3, Uber3MaterialCompiler),
            'MAPPING': (self.editor.create_mapping_node, MappingNodeCompiler),
        }

        if node_type not in node_compilers:
            raise UnsupportedNode(node_type)

        return node_compilers[node_type]

    def getFakeXMLNode(self, name):
        # is there an existing fake node I can reuse?
        return self.fakeXMLNodes.get(name)

    def registerFakeXMLNode(self, name, node):
        # store fake XML node reference so it could be reused in links in this material
        self.fakeXMLNodes[name] = node

    def compile(self, root_node):
        return self.compile_node(root_node)

    def compile_node(self, node, depth=0, ignore_uv_lookup_node=False):
        if ignore_uv_lookup_node and self.is_node_uv_lookup(node):
            return None

        node_name = node.get('name')
        node_type = node.get('type')
        if node_name in self.compiled_nodes:
            return self.compiled_nodes[node_name]
        log('  ' * depth, node_name, node_type)

        node_compiler, node_instance = self.create_compiler_for_node(node_type, depth)

        for param in node.iter(tag='param'):
            param_type = param.get('type')
            param_name = param.get('name')
            param_value = param.get('value')
            log('  ' * depth, 'param', param_name, param_type)

            input_socket = node_compiler.get_input_socket(param_name)

            if input_socket:
                if 'connection' == param_type:
                    value = node_compiler.compile_input_node(param_name, param_value)
                    if value is None:  # Node should be ignored
                        continue
                    self.link_node(input_socket, value)
                else:
                    result_node = node_compiler.compile_input_value(param_name, param_value)
                    node_compiler.set_socket_value(input_socket, result_node)
            else:
                node_compiler.compile_input_special(param_name, param_value)
        node_compiler.update_node()

        self.compiled_nodes[node_name] = node_instance
        return node_instance

    def link_node(self, socket, node):
        self.editor.link_nodes(node, socket)

    def create_compiler_for_node(self, node_type, depth):
        create_node_instance, create_node_compiler = self.get_node_compiler(node_type)
        node_instance = create_node_instance()
        node_compiler = create_node_compiler()
        node_compiler.compiler = self
        node_compiler.node_instance = node_instance
        node_compiler.depth = depth
        return node_compiler, node_instance

    def is_node_uv_lookup(self, node_info):
        if not node_info.get('type') == 'INPUT_LOOKUP':
            return False
        for param in node_info.iter(tag='param'):
            param_name = param.get('name')
            param_value = int(param.get('value'))
            if param_name == 'value' and param_value == 0:
                return True
        return False


class MaterialImageLoader:
    def __init__(self, load_image, root_folder, material_folder, copy_image=None):
        self.root_folder = root_folder
        self.material_folder = material_folder
        self._copy_image = copy_image
        self._load_image = load_image

    def load_image(self, fpath):
        if self._copy_image is None:
            if '\\' in fpath or '/' in fpath:  # texture is in common textures folder?
                fpath_full = self.root_folder + '/' + fpath
            else:
                fpath_full = self.material_folder + '/' + fpath
            return self._load_image(fpath_full)
        else:
            if '\\' in fpath or '/' in fpath:  # texture is in common textures folder?
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
    root = tree.getroot()
    root_node_name = root.attrib.get("closure_node")
    for material_name, nodes in iter_materials(root):
        if root_node_name is None:
            # MaterialLibrary 1.0 uses the material name for root node name
            root_node = nodes.get(material_name)
        else:
            # MaterialLibrary 2.0 uses attribute "closure_node" to define at root node
            root_node = nodes.get(root_node_name)
        return Compiler(nodes, material_editor, image_loader).compile(root_node)
