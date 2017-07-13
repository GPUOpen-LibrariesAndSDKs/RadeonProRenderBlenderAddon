import sys

sys.path.append('../../bindings/pyrpr/src')
import material_import
from material_import import UnsupportedNode

from pathlib import Path

import pytest


def compile(material_xml, editor):
    return material_import.compile_material_from_xml(material_xml, editor, editor)


class _Socket:

    def __init__(self, node, name):
        self.name = name
        self.node = node


class _Input:

    def __init__(self, kind, connection):
        self.kind = kind
        self.connection = connection


class Node:

    _all_sockets = []

    def __init__(self):
        self.inputs = {}

    def get_input_socket_by_name(self, name):
        if name in self._all_sockets:
            return _Socket(self, name)

    def set_input_socket_value_by_name(self, name, value):
        assert name in self._all_sockets
        self.inputs[name] = value

    def set_input_socket_value(self, socket, value):
        assert socket.name in self._all_sockets
        assert socket.node is self
        self.inputs[socket.name] = value

    def _attach_input(self, socket_name, connection):
        assert socket_name in self._all_sockets
        self.inputs[socket_name] = _Input('connection', connection)


class Material(Node):

    def __init__(self, type=None, all_sockets=None):
        super().__init__()
        if type:
            self.type = type
        if all_sockets is not None:
            self._all_sockets = all_sockets

    def __str__(self):
        return self.__class__.__name__ + ' - ' + 'inputs: ' + str(self.inputs)

    def get_output_socket(self):
        pass


class EmissiveMaterial(Material):
    type = 'emissive'
    _all_sockets = {'color', 'normal'}


class WardMaterial(Material):
    type = 'ward'
    _all_sockets = {'color', 'normal', 'roughness_x', 'roughness_y', 'rotation'}


class DiffuseMaterial(Material):
    type = 'diffuse'
    _all_sockets = {'color', 'normal'}


class ValueNode(Node):

    def __init__(self, type, all_sockets=None):
        super().__init__()
        self.type = type
        if all_sockets is not None:
            self._all_sockets = all_sockets


class Lookup(Node):
    type = 'lookup'

    lookup_type = None

    def set_type(self, type):
        self.lookup_type = type


class ImageTexture(Node):
    type = 'image_texture'

    _all_sockets = {'mapping'}

    def set_image(self, name):
        self.image_name = name


class Bumpmap(Node):

    type = 'bumpmap'

    _all_sockets = {'map', 'mapping'}

    scale = None

    def set_scale_value(self, value):
        self.scale = value

class Normalmap(Node):

    type = 'normalmap'

    _all_sockets = {'map', 'mapping'}

    scale = None

    def set_scale_value(self, value):
        self.scale = value


class MathNode(ValueNode):

    op = None

    _all_sockets = ['operand_0', 'operand_1']

    def __init__(self):
        super().__init__('math')

    def _attach_input(self, socket_name, connection):
        self.inputs[socket_name] = _Input('connection', connection)

    def set_operand_value(self, i, value):
        self.inputs['operand_'+str(i)] = value

    def get_input_operand_socket(self, i):
        return _Socket(self, 'operand_'+str(i))


class MaterialEditor:
    def __init__(self):
        self.images = []

    def create_emissive_material_node(self):
        return EmissiveMaterial()

    def create_diffuse_material_node(self):
        return DiffuseMaterial()

    def create_microfacet_material_node(self):
        return Material('microfacet',
                        all_sockets={'color', 'normal', 'roughness'})

    def create_microfacet_refraction_material_node(self):
        return Material('microfacet_refraction',
                        all_sockets={'color', 'normal', 'roughness', 'ior'})

    def create_reflection_material_node(self):
        return Material('reflection',
                        all_sockets={'color', 'normal', })

    def create_refraction_material_node(self):
        return Material('refraction',
                        all_sockets={'color', 'normal', 'ior'})

    def create_blend_material_node(self):
        return Material('blend',
                        all_sockets={'shader1', 'shader2', 'weight'})

    def create_transparent_material_node(self):
        return Material('transparent',
                        all_sockets={'color'})

    def create_oren_nayar_material_node(self):
        return Material('oren_nayar',
                        all_sockets={'color', 'normal', 'roughness'})

    def create_image_texture_node(self):
        return ImageTexture()

    def create_bumpmap_node(self):
        return Bumpmap()

    def create_normalmap_node(self):
        return Normalmap()

    def create_math_node(self):
        return MathNode()

    def create_noise2d_node(self):
        return ValueNode('noise2d', all_sockets={'mapping'})

    def create_checker_node(self):
        return ValueNode('noise2d', all_sockets={'mapping'})

    def create_blend_value_node(self):
        return ValueNode('blend_value',
                         all_sockets={'value1', 'value2', 'weight'})

    def create_fresnel_schlick_node(self):
        return ValueNode('fresnel_schlick',
                         all_sockets={'reflectance', 'normal', 'in_vec'})

    def create_fresnel_node(self):
        return ValueNode('fresnel',
                         all_sockets={'ior', 'normal', 'in_vec'})

    def link_nodes(self, source_node, input_socket):
        input_socket.node._attach_input(input_socket.name, source_node)

    def create_input_lookup_node(self):
        return Lookup()

    def load_image(self, fpath):
        self.images.append(fpath)
        return 'image#%s' % len(self.images)

    def create_ward_material_node(self):
        return WardMaterial()


def test_emissive():
    # path = sys.argv[1]
    # path = r'C:\tmp\Copper_Old\Copper_Old.xml'

    material_xml = '''
<material name="Simple_Emissive" version="0x10000236">
    <description></description>
    <node name="Simple_Emissive" type="EMISSIVE">
        <param name="color" type="float4" value="0.5, 1.0, 0.25, 0"/>
    </node>
</material>'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    assert 'emissive' == result.type
    assert result.inputs == {'color': (0.5, 1.0, 0.25, 0)}

    material_xml = '''
<material name="Simple_Emissive" version="0x10000236">
    <description></description>
    <node name="Simple_Emissive" type="EMISSIVE">
        <param name="color" type="connection" value="lookup_something_cool"/>
    </node>
    <node name="lookup_something_cool" type="INPUT_LOOKUP">
        <param name="value" type="uint" value="0"/>
    </node>
</material>'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    assert 'connection' == result.inputs['color'].kind
    assert 'lookup' == result.inputs['color'].connection.type
    assert 'UV' == result.inputs['color'].connection.lookup_type


def test_diffuse():
    material_xml = '''
<material name="Simple_Diffuse" version="0x10000236">
    <description></description>
    <node name="Simple_Diffuse" type="DIFFUSE">
        <param name="color" type="float4" value="0.5, 1.0, 0.25, 0"/>
    </node>
</material>'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    assert 'diffuse' == result.type
    assert result.inputs == {'color': (0.5, 1.0, 0.25, 0)}

def test_diffuse_normalmap():
    material_xml = '''
<material name="Simple_Diffuse" version="0x10000236">
    <description></description>
    <node name="Simple_Diffuse" type="DIFFUSE">
        <param name="normal" type="connection" value="normalmap0"/>
    </node>
    <node name="normalmap0" type="NORMAL_MAP">
        <param name="uv" type="connection" value="uv0"/>
        <param name="bumpscale" type="float4" value="0.5, 0.1, 5.0, 0"/>
        <param name="data" type="connection" value="image_file1"/>
        <param name="gamma" type="float" value="1.000000"/>
    </node>
    <node name="image_file1" type="INPUT_TEXTURE">
        <param name="path" type="file_path" value="hemisphere.png"/>
    </node>
    <node name="uv0" type="INPUT_LOOKUP">
        <param name="value" type="uint" value="0"/>
    </node>
</material>'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    assert 'normalmap' == result.inputs['normal'].connection.type

    normalmap = result.inputs['normal'].connection

    normalmap.inputs['map']

    assert 0.5 == normalmap.scale


def test_diffuse_textured():
    material_xml = r'''
<material name="Simple_Diffuse_Bumpmap_Textured" version="0x10000236">
    <description></description>
    <node name="Simple_Diffuse_Bumpmap_Textured" type="DIFFUSE">
        <param name="color" type="connection" value="texture0"/>
        <param name="normal" type="connection" value="bumpmap0"/>
    </node>
    <node name="texture0" type="IMAGE_TEXTURE">
        <param name="data" type="connection" value="image_file0"/>
        <param name="uv" type="connection" value="uv0"/>
    </node>
    <node name="image_file0" type="INPUT_TEXTURE">
        <param name="path" type="file_path" value="maps\striped_gradients.png"/>
    </node>
    <node name="bumpmap0" type="BUMP_MAP">
        <param name="uv" type="connection" value="uv0"/>
        <param name="bumpscale" type="float4" value="0.05, 0.5, 5.0, 0"/>
        <param name="data" type="connection" value="image_file1"/>
    </node>
    <node name="image_file1" type="INPUT_TEXTURE">
        <param name="path" type="file_path" value="hemisphere.png"/>
    </node>
    <node name="uv0" type="INPUT_LOOKUP">
        <param name="value" type="uint" value="0"/>
    </node>
</material>
'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    assert 'diffuse' == result.type

    assert 'image_texture' == result.inputs['color'].connection.type
    image_texture = result.inputs['color'].connection
    image_index = material_editor.images.index(r'maps\striped_gradients.png')
    assert r'maps\striped_gradients.png' in material_editor.images

    assert 'lookup' == image_texture.inputs['mapping'].connection.type
    assert 'image#%s'%(image_index+1) == image_texture.image_name

    normal_input = result.inputs['normal']

    assert 'bumpmap' == normal_input.connection.type
    bumpmap = normal_input.connection
    assert 0.05 == bumpmap.scale
    assert 'lookup' == bumpmap.inputs['mapping'].connection.type
    assert 'image_texture' == bumpmap.inputs['map'].connection.type
    bumpmap_image = bumpmap.inputs['map'].connection
    assert r'hemisphere.png' in material_editor.images
    image_index = material_editor.images.index(r'hemisphere.png')
    assert image_index!=-1

    assert 'image#%s'%(image_index+1) == bumpmap_image.image_name


def test_shared_node():
    material_xml = r'''
<material name="SharedNode" version="0x10000236">
    <description></description>
    <node name="SharedNode" type="DIFFUSE">
        <param name="color" type="connection" value="uv0"/>
        <param name="normal" type="connection" value="uv0"/>
    </node>
    <node name="uv0" type="INPUT_LOOKUP">
        <param name="value" type="uint" value="0"/>
    </node>
</material>
'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)

    assert result.inputs['color'].connection is result.inputs['normal'].connection


def test_noise2d():
    material_xml = r'''
<material name="Simple_Noise2d" version="0x10000236">
    <description></description>
    <node name="Simple_Noise2d" type="DIFFUSE">
        <param name="color" type="connection" value="texture0"/>
    </node>
    <node name="texture0" type="NOISE2D_TEXTURE">
        <param name="uv" type="connection" value="uv0"/>
    </node>

    <node name="uv0" type="ARITHMETIC">
        <param name="color0" type="connection" value="uvinput0"/>
        <param name="color1" type="float4" value="5, 5, 0, 0"/>
        <param name="op" type="uint" value="2"/>
    </node>

    <node name="uvinput0" type="INPUT_LOOKUP">
        <param name="value" type="uint" value="0"/>
    </node>
</material>
'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)

    assert 'noise2d' == result.inputs['color'].connection.type
    noise2d = result.inputs['color'].connection

    'math' == noise2d.inputs['mapping'].connection.type


def test_fresnel():
    material_xml = r'''
<material name="Simple_Fresnel" version="0x10000236">
    <description></description>
    <node name="Simple_Fresnel" type="DIFFUSE">
        <param name="color" type="connection" value="texture0"/>
    </node>
    <node name="texture0" type="FRESNEL">
        <param name="normal" type="connection" value="normalmap0"/>
        <param name="invec" type="connection" value="uv0"/>
        <param name="ior" type="float4" value="1.52, 0.0, 0.0, 0"/>
    </node>
    <node name="normalmap0" type="NORMAL_MAP">
        <param name="data" type="connection" value="image_file1"/>
        <param name="bumpscale" type="float4" value="0.9, 0, 0, 0"/>
    </node>
    <node name="image_file1" type="INPUT_TEXTURE">
        <param name="path" type="file_path" value="maps\normals.png"/>
    </node>
    <node name="uv0" type="INPUT_LOOKUP">
        <param name="value" type="uint" value="3"/>
    </node>
</material>
'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)

    assert 'fresnel' == result.inputs['color'].connection.type
    fresnel = result.inputs['color'].connection

    assert abs(1.52-fresnel.inputs['ior']) < 0.0001
    assert 'lookup' == fresnel.inputs['in_vec'].connection.type

    assert 'normalmap' == fresnel.inputs['normal'].connection.type


def test_fresnel_schlick():
    material_xml = r'''
<material name="Simple_FresnelSchlick" version="0x10000236">
    <description></description>
    <node name="Simple_FresnelSchlick" type="DIFFUSE">
        <param name="color" type="connection" value="texture0"/>
    </node>
    <node name="texture0" type="FRESNEL_SCHLICK">
        <param name="normal" type="connection" value="normalmap0"/>
        <param name="invec" type="connection" value="uv0"/>
        <param name="reflectance" type="float4" value="0.5, 0.0, 0.0, 0"/>
    </node>
    <node name="normalmap0" type="NORMAL_MAP">
        <param name="data" type="connection" value="image_file1"/>
        <param name="bumpscale" type="float4" value="0.9, 0, 0, 0"/>
    </node>
    <node name="image_file1" type="INPUT_TEXTURE">
        <param name="path" type="file_path" value="maps\normals.png"/>
    </node>
    <node name="uv0" type="INPUT_LOOKUP">
        <param name="value" type="uint" value="3"/>
    </node>
</material>
'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)

    assert 'fresnel_schlick' == result.inputs['color'].connection.type
    fresnel = result.inputs['color'].connection

    assert abs(0.5-fresnel.inputs['reflectance']) < 0.0001
    assert 'lookup' == fresnel.inputs['in_vec'].connection.type

    assert 'normalmap' == fresnel.inputs['normal'].connection.type


def test_arithmetic():
    material_xml = r'''
<material name="Simple_Emissive" version="0x10000236">
    <description></description>
    <node name="Simple_Emissive" type="EMISSIVE">
        <param name="color" type="connection" value="arithm0"/>
    </node>
    <node name="arithm0" type="ARITHMETIC">
        <param name="color0" type="connection" value="Map #180"/>
        <param name="color1" type="float4" value="3, 14, 2.5, 9"/>
        <param name="op" type="uint" value="2"/>
    </node>
    <node name="Map #180" type="IMAGE_TEXTURE">
        <param name="data" type="connection" value="box0"/>
    </node>
    <node name="box0" type="INPUT_TEXTURE">
        <param name="path" type="file_path" value="RadeonProRMaps\brass_matte0002.png"/>
    </node>
</material>'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    color_input = result.inputs['color']

    assert 'math' == color_input.connection.type
    math_node = color_input.connection

    assert 'MUL' == math_node.op

    assert 'image_texture' == math_node.inputs['operand_0'].connection.type
    assert (3, 14, 2.5, 9) == math_node.inputs['operand_1']


    material_xml = r'''
<material name="Simple_Math" version="0x10000236">
    <description></description>
    <node name="Simple_Math" type="EMISSIVE">
        <param name="color" type="connection" value="arithm0"/>
    </node>
    <node name="arithm0" type="ARITHMETIC">
        <param name="color0" type="float4" value="1, 1, 1, 1"/>
        <param name="op" type="uint" value="4"/>
    </node>
</material>'''
    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    result = compile(material_xml, material_editor)
    color_input = result.inputs['color']

    assert 'math' == color_input.connection.type
    math_node = color_input.connection
    assert 'SIN' == math_node.op
    assert (1, 1, 1, 1) == math_node.inputs['operand_0']


def test_ward():
    material_xml = '''
<material name="Simple_Ward" version="0x10000236">
    <description></description>
    <node name="Simple_Ward" type="WARD">
        <param name="color" type="float4" value="0.5, 1.0, 0.25, 0"/>
        <param name="roughness_x" type="float4" value="0.1, 0.1, 0.1, 0"/>
        <param name="roughness_y" type="connection" value="image_texture0"/>
        <param name="rotation" type="float4" value="1.0, 0.5, 0, 0"/>
    </node>
    <node name="image_texture0" type="IMAGE_TEXTURE">
        <param name="data" type="connection" value="input_texture0"/>
    </node>
    <node name="input_texture0" type="INPUT_TEXTURE">
        <param name="path" type="file_path" value="maps\striped_gradients.png"/>
    </node>
</material>'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    assert 'ward' == result.type
    assert (0.5, 1.0, 0.25, 0) == result.inputs['color']
    assert 1.0 == result.inputs['rotation']  # taking only first float to pass to blender node
    assert 0.1 == result.inputs['roughness_x']  # taking only first float to pass to blender node


def test_microfacet():
    material_xml = '''
<material name="Simple_Microfacet" version="0x10000236">
    <description></description>
    <node name="Simple_Microfacet" type="MICROFACET">
        <param name="color" type="float4" value="0.5, 1.0, 0.25, 0"/>
        <param name="normal" type="float4" value="0, 1, 0, 0"/>
        <param name="roughness" type="float4" value="0.25, 0, 0, 0"/>
    </node>
</material>'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    assert 'microfacet' == result.type
    assert (0.5, 1.0, 0.25, 0) == result.inputs['color']
    assert (0.0, 1.0, 0.0, 0) == result.inputs['normal']
    assert 0.25 == result.inputs['roughness']  # taking only first float to pass to blender node


def test_microfacet_refraction():
    material_xml = '''
<material name="Simple_MicrofacetRefraction" version="0x10000236">
    <description></description>
    <node name="Simple_MicrofacetRefraction" type="MICROFACET_REFRACTION">
        <param name="color" type="float4" value="1, 1.0, 1, 0"/>
        <param name="normal" type="connection" value="normalmap0"/>
        <param name="roughness" type="float4" value="1.0, 0, 0, 0"/>
        <param name="ior" type="float4" value="1.52, 0.5, 0, 0"/>
    </node>
    <node name="normalmap0" type="NORMAL_MAP">
        <param name="bumpscale" type="float4" value="0.5, 0.5, 0.5, 0"/>
        <param name="data" type="connection" value="image_file1"/>
    </node>
    <node name="image_file1" type="INPUT_TEXTURE">
        <param name="path" type="file_path" value="maps/normals.png"/>
    </node>
</material>'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    assert 'microfacet_refraction' == result.type
    assert (1.0, 1.0, 1.0, 0) == result.inputs['color']
    assert 1.0 == result.inputs['roughness']  # taking only first float to pass to blender node
    assert abs(1.52-result.inputs['ior']) < 0.001  # taking only first float to pass to blender node
    assert 'normalmap' == result.inputs['normal'].connection.type


def test_reflection():
    material_xml = '''
<material name="Simple_Reflection" version="0x10000236">
    <description></description>
    <node name="Simple_Reflection" type="REFLECTION">
        <param name="color" type="float4" value="0.5, 1.0, 0.25, 0"/>
        <param name="normal" type="float4" value="0, 1, 0, 0"/>
    </node>
</material>'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    assert 'reflection' == result.type
    assert (0.5, 1.0, 0.25, 0) == result.inputs['color']
    assert (0.0, 1.0, 0.0, 0) == result.inputs['normal']


def test_refraction():
    material_xml = r'''
<material name="Simple_Refraction_Normalmap" version="0x10000236">
    <description></description>
    <node name="Simple_Refraction_Normalmap" type="REFRACTION">
        <param name="color" type="float4" value="1, 1.0, 1, 0"/>
        <param name="normal" type="connection" value="normalmap0"/>
        <param name="ior" type="float4" value="1.52, 0.5, 0, 0"/>
    </node>
    <node name="normalmap0" type="NORMAL_MAP">
        <param name="bumpscale" type="float4" value="0.4, 0.0, 0.0, 0"/>
        <param name="data" type="connection" value="image_file1"/>
    </node>
    <node name="image_file1" type="INPUT_TEXTURE">
        <param name="path" type="file_path" value="maps\normals.png"/>
    </node>
</material>'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    assert 'refraction' == result.type
    assert (1.0, 1.0, 1.0, 0) == result.inputs['color']
    assert abs(1.52-result.inputs['ior']) < 0.001  # taking only first float to pass to blender node
    assert 'normalmap' == result.inputs['normal'].connection.type


def test_transparent():
    material_xml = '''
<material name="Simple_Transparent" version="0x10000236">
    <description></description>
    <node name="Simple_Transparent" type="TRANSPARENT">
        <param name="color" type="float4" value="1.0, 0.5, 0.1, 1"/>
    </node>
</material>'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    assert 'transparent' == result.type
    assert (1.0, 0.5, 0.1, 1) == result.inputs['color']


def test_blend():
    material_xml = '''
<material name="Simple_Blend" version="0x10000236">
    <description></description>
    <node name="Simple_Blend" type="BLEND">
        <param name="color0" type="connection" value="A"/>
        <param name="color1" type="connection" value="B"/>
        <param name="weight" type="float4" value="0.25, 0, 0, 0"/>
    </node>
    <node name="A" type="DIFFUSE">
        <param name="color" type="float4" value="1.0, 1.0, 0.0, 0"/>
    </node>
    <node name="B" type="DIFFUSE">
        <param name="color" type="float4" value="0.0, 0.0, 1.0, 0"/>
    </node>

</material>'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    assert 'blend' == result.type
    assert (1.0, 1.0, 0.0, 0) == result.inputs['shader1'].connection.inputs['color']
    assert (0.0, 0.0, 1.0, 0) == result.inputs['shader2'].connection.inputs['color']

    assert 'weight' in result.inputs
    assert 0.25 == result.inputs['weight']


def test_oren_nayar():
    material_xml = r'''
<material name="Simple_OrenNayar" version="0x10000236">
    <description></description>
    <node name="Simple_OrenNayar" type="ORENNAYAR">
        <param name="color" type="float4" value="1.0, 1.0, 1.0, 0"/>
        <param name="normal" type="connection" value="normalmap0"/>
        <param name="roughness" type="float4" value="0.5, 0, 0, 0"/>
    </node>
    <node name="normalmap0" type="NORMAL_MAP">
        <param name="bumpscale" type="float4" value="0.9, 0.0, 0.0, 0"/>
        <param name="data" type="connection" value="image_file1"/>
    </node>
    <node name="image_file1" type="INPUT_TEXTURE">
        <param name="path" type="file_path" value="maps\normals.png"/>
    </node>
</material>
'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    assert 'oren_nayar' == result.type
    assert (1.0, 1.0, 1.0, 0) == result.inputs['color']
    assert 0.5 == result.inputs['roughness']  # taking only first float to pass to blender node
    assert 'normalmap' == result.inputs['normal'].connection.type


def test_blendvalue():
    material_xml = '''
<material name="Simple_BlendValue" version="0x10000236">
    <description></description>
    <node name="Simple_BlendValue" type="DIFFUSE">
        <param name="color" type="connection" value="blendvalue0"/>
    </node>
    <node name="blendvalue0" type="BLEND_VALUE">
        <param name="color0" type="float4" value="1, 0, 0, 0"/>
        <param name="color1" type="float4" value="0, 1, 0, 0"/>
        <param name="weight" type="float4" value="0.3, 0, 0, 1"/>
    </node>
</material>'''

    material_editor = MaterialEditor()

    result = compile(material_xml, material_editor)
    assert 'blend_value' == result.inputs['color'].connection.type
    blend_value = result.inputs['color'].connection
    assert (1.0, 0.0, 0.0, 0) == blend_value.inputs['value1']
    assert (0.0, 1.0, 0.0, 0) == blend_value.inputs['value2']

    assert abs(0.3-blend_value.inputs['weight']) < 0.001


@pytest.mark.skip
def test_production_library():
    material_library_path = str(Path.home()/'Documents/Radeon ProRender/Blender/Material Library')

    good = set()
    bad = set()
    unsupported_nodes = set()
    missing_images = {}
    for path in Path(material_library_path).iterdir():
        name = path.name
        fpath = path/(name + '.xml')
        if fpath.is_file():
            print(fpath)
            material_editor = MaterialEditor()

            try:
                result = compile(fpath.read_text(), material_editor)
            except UnsupportedNode as e:
                bad.add(name)
                unsupported_nodes.add(e.node_type)
            else:
                good.add(name)
            for image in material_editor.images:
                if '\\' in image:
                    if not (Path(material_library_path)/image).is_file():
                        missing_images.setdefault(name, set()).add(image)

    assert not(good & bad)
    print(' '.join(good))
    if unsupported_nodes:
        print('unsupported_nodes:', ' '.join(unsupported_nodes))

    print('good:', len(good))
    print('bad:', len(bad))

    if missing_images:
        print('missing_images:')
        for material in missing_images:
            print('    -', material)
            print('        ', '        '.join(missing_images[material]))
