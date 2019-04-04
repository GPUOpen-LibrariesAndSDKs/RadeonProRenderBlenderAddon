import ast
from xml.etree import ElementTree   # for some reason Blender doesn't allow access via xml.etree.ElementTree

import bpy
from rprblender.utils.logging import Log
log = Log(tag='material_loader')


class UnsupportedNode(Exception):
    def __init__(self, node_type):
        super().__init__("Unsupported node:", node_type)
        self.node_type = node_type


class RPRXMLMaterialCompiler:
    """ Load nodes tree info from XML and create nodes in shader node tree using this info """
    def __init__(self, xml_nodes, tree: bpy.types.ShaderNodeTree, image_loader):
        self.xml_nodes = xml_nodes

        self.tree = tree
        self.image_loader = image_loader
        self.compiled_nodes = {}

    def compile(self, node: ElementTree.Element) -> bpy.types.ShaderNode:
        """ Material parsing entry point - create and link nodes by XML info starting from closure """
        closure = self.compile_node(node)
        log("closure node '{}' is '{}'".format(node, closure))
        return closure

    def compile_node(self, node: ElementTree.Element, depth: int = 0, ignore_uv_lookup_node=False):
        """ Compile new node by node info or return known, compile links in depth """
        if not node:
            return None

        # Special case for Image Texture to ignore attached UV Lookup
        if ignore_uv_lookup_node and self.is_node_uv_lookup(node):
            return None

        node_name = node.get('name')
        node_type = node.get('type')

        # node is already parsed?
        if node_name in self.compiled_nodes:
            return self.compiled_nodes[node_name]

        log('  ' * depth, node_name, node_type)

        # create node instance and compiler for it
        node_instance, node_compiler = self.create_instance_for_node(node_type, depth)

        for param in node.iter(tag='param'):
            connection_type = param.get('type')  # linked node or value
            input_name = param.get('name')
            input_value = param.get('value')  # value to assign or node name to parse and link
            log('  ' * depth, 'param', input_name, connection_type)

            # try to get node input socket with that name
            input_socket = node_compiler.get_input_socket(input_name)

            if not input_socket:
                # it could be the node-specific case of UI enum/checkbox, let the node compiler handle it
                node_compiler.compile_input_special(input_name, input_value)
                continue

            # linked node
            if 'connection' == connection_type:
                linked_node = node_compiler.compile_input_node(input_name, input_value)
                if linked_node:  # ignored nodes will return None, wrong will raise UnsupportedNode exception
                    self.link_node(linked_node, input_socket)
                continue

            # assigned float/color/vector value
            result_value = node_compiler.compile_input_value(input_name, input_value)
            node_compiler.set_socket_value(input_socket, result_value)

        # node-specific update
        node_compiler.update_node()

        self.compiled_nodes[node_name] = node_instance
        return node_instance

    def link_node(self, node: bpy.types.ShaderNode, input_socket, ):
        """ Link node output to socket """
        output = node.outputs[0]
        self.tree.links.new(output, input_socket)

    def get_xml_node_info(self, node_name: str):
        return self.xml_nodes.get(node_name, None)

    def get_node_compiler(self, node_type):
        """ Find RPR/Blender node type and XML node compiler """
        if node_type not in node_compilers:
            raise UnsupportedNode(node_type)
        return node_compilers[node_type]

    def create_instance_for_node(self, node_type, depth):
        """ Create node instance and compiler for it by node_type """
        node_blender_type, node_compiler_class = self.get_node_compiler(node_type)

        node_instance = self.tree.nodes.new(type=node_blender_type)

        node_compiler = node_compiler_class(self, node_instance, depth)

        return node_instance, node_compiler

    def is_node_uv_lookup(self, node_info: ElementTree.Element):
        """ Check if this is "Lookup" node in "UV" mode; used to ignore UV Lookup attached to Image Texture nodes """
        if not node_info.get('type') == 'INPUT_LOOKUP':
            return False
        for param in node_info.iter(tag='param'):
            param_name = param.get('name')
            param_value = int(param.get('value'))
            if param_name == 'value' and param_value == 0:
                return True
        return False

    def load_image(self, path):
        return self.image_loader.load_image(path)


# support class for node compilers
class MatLibSocketInfo:
    """ Store RPR node socket info - Blender name, value type, socket to update if this socket value/link set """
    def __init__(self, name: str, type_name: str, socket_to_update: str = ''):
        self.name = name
        self.type_name = type_name
        self.socket_to_update = socket_to_update


##
# node compilers

class BasicNodeCompiler:
    """ Base class for XML node parser to assign XML values to Blender node inputs """
    def __init__(self, compiler: RPRXMLMaterialCompiler, node_instance: bpy.types.ShaderNode, depth: int):
        self.compiler = compiler
        self.node_instance = node_instance
        self.depth = depth

    # Values conversion
    @staticmethod
    def get_float4_first_component(value: str):
        """ Get float from string of vector4 """
        return ast.literal_eval(value)[0]

    @staticmethod
    def get_float4_as_float2(value: str):
        """ Get vector2 from string of vector4 """
        return ast.literal_eval(value)[0:2]

    @staticmethod
    def get_float4_as_float3(value: str):
        """ Get vector 3 from string of vector4 """
        return ast.literal_eval(value)[0:3]

    # compile methods
    def compile_input_node(self, socket_name: str, node_name: str):
        """ Compile linked node node_name and link to socket socket_name """
        node_info = self.compiler.get_xml_node_info(node_name)
        if not node_info:
            # no need to parse node if socket not found
            return None
        return self.compiler.compile_node(node_info, self.depth + 1)

    def compile_input_value(self, socket_name: str, value):
        """ Convert value from string and assign it to socket socket_name """
        return ast.literal_eval(value)

    def compile_input_special(self, socket_name: str, value):
        """ in case input is not converted directly to blender socket input, like Uber UI enums/checkboxes """
        log.warn('compile_input_special fails (socket_name: {}, value: {})'.format(socket_name, value))

    def get_input_socket(self, socket_name: str):
        return self.node_instance.inputs.get(socket_name, None)

    def set_socket_value(self, socket, value):
        try:
            socket.default_value = value
        except Exception:
            log.error("Failure setting socket {}:{} to value {}".format(socket.name, socket, value))
            raise

    def update_node(self):
        """ Post-import update if needed """
        pass


class MappedNodeCompiler(BasicNodeCompiler):
    """ Used as a base in cases when library inputs could be mapped to node inputs by simple table """
    input_sockets_info = {}  # {xml_input_name: MatLibSocketInfo(node input name, value type, socket to update)}

    def get_input_socket(self, name):
        socket_info = self.input_sockets_info.get(name, None)
        if not socket_info:
            return None

        return super().get_input_socket(socket_info.name)

    def compile_input_value(self, name, value):
        """ Convert XML float4 string to required format """
        socket_info = self.input_sockets_info.get(name)
        if socket_info is None:
            return None

        if socket_info.type_name == 'float3':
            return self.get_float4_as_float3(value)

        if socket_info.type_name == 'float':
            return self.get_float4_first_component(value)

        if socket_info.type_name == 'int':
            return int(self.get_float4_first_component(value))

        if socket_info.type_name == 'bool':
            return bool(self.get_float4_first_component(value))

        return super().compile_input_value(name, value)


class UberMaterialCompiler(MappedNodeCompiler):
    """ RPR Uber shader node importer """
    # inputs mapping
    input_sockets_info = {
        'diffuse.color': MatLibSocketInfo('Diffuse Color', 'float4', 'enable_diffuse'),
        'diffuse.weight': MatLibSocketInfo('Diffuse Weight', 'float', 'enable_diffuse'),
        'diffuse.roughness': MatLibSocketInfo('Diffuse Roughness', 'float', 'enable_diffuse'),
        'reflection.color': MatLibSocketInfo('Reflection Color', 'float4', 'enable_reflection'),
        'reflection.weight': MatLibSocketInfo('Reflection Weight', 'float', 'enable_reflection'),
        'reflection.roughness': MatLibSocketInfo('Reflection Roughness', 'float', 'enable_reflection'),
        'reflection.anisotropy': MatLibSocketInfo('Reflection Anisotropy', 'float', 'enable_reflection'),
        'reflection.anistropyRotation': MatLibSocketInfo('Reflection Anisotropy Rotation', 'float', 'enable_reflection'),
        'reflection.ior': MatLibSocketInfo('Reflection IOR', 'float', 'enable_reflection'),
        'refraction.color': MatLibSocketInfo('Refraction Color', 'float4', 'enable_refraction'),
        'refraction.weight': MatLibSocketInfo('Refraction Weight', 'float', 'enable_refraction'),
        'refraction.roughness': MatLibSocketInfo('Refraction Roughness', 'float', 'enable_refraction'),
        'refraction.ior': MatLibSocketInfo('Refraction IOR', 'float', 'enable_refraction'),
        'refraction.absorptionColor': MatLibSocketInfo('Refraction Absorption Color', 'float4', 'enable_refraction'),
        'refraction.absorptionDistance': MatLibSocketInfo('Refraction Absorption Distance', 'float', 'enable_refraction'),
        'coating.color': MatLibSocketInfo('Coating Color', 'float4', 'enable_coating'),
        'coating.weight': MatLibSocketInfo('Coating Weight', 'float', 'enable_coating'),
        'coating.roughness': MatLibSocketInfo('Coating Roughness', 'float', 'enable_coating'),
        'coating.ior': MatLibSocketInfo('Coating IOR', 'float', 'enable_coating'),
        'coating.metalness': MatLibSocketInfo('Coating Metalness', 'float', 'enable_coating'),
        'coating.transmissionColor': MatLibSocketInfo('Coating Transmission Color', 'float4', 'enable_coating'),
        'coating.thickness': MatLibSocketInfo('Coating Thickness', 'float', 'enable_coating'),
        'sheen.weight': MatLibSocketInfo('Sheen Weight', 'float', 'enable_sheen'),
        'sheen': MatLibSocketInfo('Sheen Color', 'float4', 'enable_sheen'),
        'sheen.tint': MatLibSocketInfo('Sheen Tint', 'float', 'enable_sheen'),
        'emission.color': MatLibSocketInfo('Emission Color', 'float4', 'enable_emission'),
        'emission.weight': MatLibSocketInfo('Emission Weight', 'float', 'enable_emission'),
        'transparency': MatLibSocketInfo('Transparency', 'float'),
        'sss.scatterColor': MatLibSocketInfo('Subsurface Color', 'float4'),
        'sss.scatterDistance': MatLibSocketInfo('Subsurface Radius', 'float3'),
        'sss.scatterDirection': MatLibSocketInfo('Subsurface Direction', 'float'),
        'sss.weight': MatLibSocketInfo('Subsurface Weight', 'float'),
        'backscatter.weight': MatLibSocketInfo('Backscatter Weight', 'float'),
        'backscatter.color': MatLibSocketInfo('Backscatter Color', 'float4'),

        # inputs that should be linked only
        'diffuse.normal': MatLibSocketInfo('Diffuse Normal', '', 'diffuse'),
        'reflection.normal': MatLibSocketInfo('Reflection Normal', '', 'reflection'),
        'refraction.normal': MatLibSocketInfo('Refraction Normal', '', 'refraction'),
        'coating.normal': MatLibSocketInfo('Coating Normal', '', 'coating'),
        'normal': MatLibSocketInfo('Normal', '', 'normal'),
        'displacement': MatLibSocketInfo('Displacement Map', '', 'displacement'),

        # additional internal input
        'reflection.metalness': MatLibSocketInfo('Reflection Metalness', 'float'),
    }

    # values that are not inputs - checkboxes, enums
    ui_fields = {
        'reflection.mode': MatLibSocketInfo('reflection_mode', 'str'),
        'refraction.thinSurface': MatLibSocketInfo('refraction_thin_surface', 'bool'),
        'refraction.caustics': MatLibSocketInfo('refraction_caustics', 'bool'),
        'coating.mode': MatLibSocketInfo('coating_mode', 'str'),
        'emission.mode': MatLibSocketInfo('emission_doublesided', 'bool'),
        'sss.multiscatter': MatLibSocketInfo('sss_multiscatter', 'bool'),

        # internal
        'sss.use.diffuse.color': MatLibSocketInfo('subsurface_use_diffuse_color', 'bool'),
        'backscatter.separate.color': MatLibSocketInfo('backscatter_separate_color', 'bool'),

        # weight and links
        'diffuse.weight': MatLibSocketInfo('enable_diffuse', 'bool'),
        'reflection.weight': MatLibSocketInfo('enable_reflection', 'bool'),
        'refraction.weight': MatLibSocketInfo('enable_refraction', 'bool'),
        'coating.weight': MatLibSocketInfo('enable_coating', 'bool'),
        'sheen.weight': MatLibSocketInfo('enable_sheen', 'bool'),
        'emission.weight': MatLibSocketInfo('enable_emission', 'bool'),
        'sss.weight': MatLibSocketInfo('enable_sss', 'bool'),
        'normal': MatLibSocketInfo('enable_normal', 'bool'),
        'transparency': MatLibSocketInfo('enable_transparency', 'bool'),
        'displacement': MatLibSocketInfo('enable_displacement', 'bool'),

        # normals
        'diffuse.normal': MatLibSocketInfo('diffuse_use_shader_normal', 'bool'),
        'reflection.normal': MatLibSocketInfo('reflection_use_shader_normal', 'bool'),
        'refraction.normal': MatLibSocketInfo('refraction_use_shader_normal', 'bool'),
        'coating.normal': MatLibSocketInfo('coating_use_shader_normal', 'int'),
    }

    sections_to_update = ('diffuse.weight', 'reflection.weight', 'refraction.weight', 'coating.weight', 'sss.weight',
                          'sheen.weight', 'emission.weight',)

    ui_values_for_import = ('reflection.mode', 'refraction.thinSurface', 'refraction.caustics', 'coating.mode',
                            'emission.mode', 'sss.multiscatter')

    def get_input_socket(self, name):
        # reflection in library stores metalness and IOR in the same input depending on reflection mode. Remap by mode
        if name == 'reflection.ior':
            mode = self.get_ui_socket_value('reflection.mode')
            if mode is not None and mode == 'METALNESS':
                name = 'reflection.metalness'

        return super().get_input_socket(name)

    def get_ui_socket_value(self, name):
        socket_info = self.ui_fields.get(name)
        if socket_info is None:
            return None

        return getattr(self.node_instance, socket_info.name)

    def get_update_socket_info(self, name):
        socket_info = self.ui_fields.get(name)
        if socket_info is None:
            return None

        return socket_info

    def set_ui_socket_value(self, name, value):
        socket_info = self.ui_fields.get(name)
        if socket_info is None:
            return

        if name in ('reflection.mode', 'coating.mode'):
            value = {'1': 'PBR', '2': 'METALNESS'}[value]
        elif name == 'emission.mode':
            value = {'1': False, '2': True}[value]
        elif socket_info.type_name == 'bool':
            value = bool(int(value))

        setattr(self.node_instance, socket_info.name, value)

    def compile_input_node(self, socket_name, linked_node):
        socket_info = self.input_sockets_info.get(socket_name)
        if socket_info is None:
            return None

        # set False for "use shader normal map" if normal map is linked to the section
        if socket_name in ('diffuse.normal', 'reflection.normal', 'refraction.normal', 'coating.normal'):
            self.set_ui_socket_value(socket_name, False)

        # enable sections for linked nodes only
        elif socket_name in ('normal', 'transparency', 'displacement'):
            self.set_ui_socket_value(socket_name, True)

            if socket_name == 'displacement':  # prevent excessive mesh distortion
                self.node_instance.node.displacement_max = 0.025

        # use separate backscatter color if any link attached to it
        if socket_name == 'backscatter.color':
            self.set_ui_socket_value('backscatter.separate.color', True)

        node_info = self.compiler.get_xml_node_info(linked_node)
        compiled_node = self.compiler.compile_node(node_info, self.depth + 1)
        return compiled_node

    def compile_input_special(self, name, value):
        if name in self.ui_values_for_import and self.get_ui_socket_value(name) is not None:
            return self.set_ui_socket_value(name, value)
        return super().compile_input_special(name, value)

    def set_socket_value(self, input_socket, value):
        # Coating Transmission Color passed as inverted, convert it back
        if input_socket.name == self.input_sockets_info['coating.transmissionColor'].name:
            value = (1.0 - value[0], 1.0 - value[1], 1.0 - value[2], 1.0)
        super().set_socket_value(input_socket, value)

    def update_node(self):
        # enable channels if weight is > 0
        for input_socket_name in self.sections_to_update:
            weight_socket = self.get_input_socket(input_socket_name)
            if weight_socket is not None:
                enabled = weight_socket.default_value > 0
                self.set_ui_socket_value(input_socket_name, enabled)

        # check for "Separate Backscatter Color": compare "diffuse.color" and "backscatter.color"
        diffuse_color = self.get_input_socket('diffuse.color').default_value
        backscatter_color = self.get_input_socket('backscatter.color').default_value
        not_equal = sum([1 for i in range(0, 4) if not diffuse_color[i] == backscatter_color[i]]) > 0
        if not_equal:
            info = self.get_update_socket_info('backscatter.separate.color')
            if info is not None:
                self.set_ui_socket_value(info.name, True)

        # check for "Subsurface Use Diffuse Color": compare "diffuse.color" and "Subsurface Scattering Color"
        subsurface_color = self.get_input_socket('sss.scatterColor').default_value
        not_equal = sum([1 for i in range(0, 4) if not diffuse_color[i] == subsurface_color[i]]) > 0
        if not_equal:
            info = self.get_update_socket_info('sss.use.diffuse.color')
            if info is not None:
                self.set_ui_socket_value(info.name, True)


class BumpNormalNodesCompiler(MappedNodeCompiler):
    """ RPR Bump and RPR Normal Map nodes importer, they use same input names """
    input_sockets_info = {
        'color': MatLibSocketInfo('Map', 'float4', ''),
        'bumpscale': MatLibSocketInfo('Scale', 'float', ''),
    }


class ImageTextureCompiler(BasicNodeCompiler):
    """ Import RPR Image Texture node, load texture file """
    def compile_input_node(self, name, value):
        uv_node_info = self.compiler.get_xml_node_info(value)
        return self.compiler.compile_node(uv_node_info, self.depth + 1, ignore_uv_lookup_node=True)

    def compile_input_special(self, input_name, value):
        # for image texture node just get its input_texture image(it's not a separate node for us in blender)
        if 'data' == input_name:
            input_texture_node = self.compiler.get_xml_node_info(value)
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
                    self.node_instance.image = self.compiler.load_image(param_value)
                elif param_name == 'gamma':
                    self.node_instance.color_space = 'SRGB' if float(param_value) > 1.0 else 'LINEAR'

                # did we have the texture tiling info as well?
                if param_name in ("tiling_u", "tiling_v"):
                    attach_mapping_node = True
                    if param_name == "tiling_u":
                        tiling_u = float(param_value)
                    elif param_name == "tiling_v":
                        tiling_v = float(param_value)

            # tiling/offset texture info in Blender stored in a separate node, create and link it
            if attach_mapping_node:
                mapping_socket = self.get_input_socket('UV')
                mapping_node = self.compiler.tree.nodes.new(type='ShaderNodeMapping')
                log("mapping node {}".format(mapping_node))
                log("mapping socket {}".format(mapping_socket))
                mapping_node.scale[0] = tiling_u
                mapping_node.scale[1] = tiling_v
                self.compiler.link_node(mapping_node, mapping_socket)

    def get_input_socket(self, name):
        if name in ['uv']:
            return super().get_input_socket('mapping')

        return super().get_input_socket(name)


class ValueBlendCompiler(MappedNodeCompiler):
    input_sockets_info = {
        'weight': MatLibSocketInfo('Fac', 'float4', ''),
        'color0': MatLibSocketInfo('Color1', 'float4', ''),
        'color1': MatLibSocketInfo('Color2', 'float4', ''),
    }


class ShaderBlendCompiler(MappedNodeCompiler):
    input_sockets_info = {
        'weight': MatLibSocketInfo('Weight', 'float4', ''),
        'color0': MatLibSocketInfo('Shader 1', 'float4', ''),
        'color1': MatLibSocketInfo('Shader 2', 'float4', ''),
    }


class EmissiveCompiler(MappedNodeCompiler):
    input_sockets_info = {
        'color': MatLibSocketInfo('Color', 'float4', ''),  # in library color is color*intensity...
    }


class RPRMathCompiler(BasicNodeCompiler):
    """ RPR Math node importer """

    operation_id_to_enum_id = {  # sorted by library id for easier maintenance
        '0': 'ADD',
        '1': 'SUB',
        '2': 'MUL',
        '3': 'DIV',
        '4': 'SIN',
        '5': 'COS',
        '6': 'TAN',
        '7': 'SELECT_X',
        '8': 'SELECT_Y',
        '9': 'SELECT_Z',
        '10': 'COMBINE',
        '11': 'DOT3',
        '12': 'CROSS3',
        '13': 'LENGTH3',
        '14': 'NORMALIZE3',
        '15': 'POW',
        '16': 'ACOS',
        '17': 'ASIN',
        '18': 'ATAN',
        '19': 'AVERAGE_XYZ',
        '20': 'AVERAGE',
        '21': 'MIN',
        '22': 'MAX',
        '23': 'FLOOR',
        '24': 'MOD',
        '25': 'ABS',
        '26': 'SHUFFLE_YZWX',
        '27': 'SHUFFLE_ZWXY',
        '28': 'SHUFFLE_WXYZ',
        # '29': 'MAT_MUL',  # unsupported by node
        '30': 'SELECT_W',
        '31': 'DOT4',
        '32': 'LOG',
    }

    socket_type: str = 'COLOR'

    def get_input_socket(self, socket_name: str):
        # operands socket names could be changed by UI, use indices instead
        if socket_name == 'color0':
            return self.node_instance.inputs[0]

        if socket_name == 'color1':
            return self.node_instance.inputs[1]

        if socket_name == 'color2':
            return self.node_instance.inputs[2]

        return None

    def compile_input_special(self, socket_name, value):
        if socket_name == 'op':
            enum_id = self.operation_id_to_enum_id.get(value, None)
            if enum_id:
                self.node_instance.operation = enum_id
                return None

        return super().compile_input_special(socket_name, value)

    def set_socket_value(self, input_socket, value):
        """ Change input sockets type to correctly display values outside of "color" values range of [0.0..1.0] """
        if isinstance(value, tuple) and self.socket_type in ('COLOR', 'FLOAT'):
            # for tuple check if it fits the "color" range, use VECTOR mode if not
            out_of_color_range = sum([0 if 0.0 <= v <= 1.0 else 1 for v in value]) > 0
            equal = len(value) == 1 or sum([0 if v == value[0] else 1 for v in value[1:]]) == 0
            if out_of_color_range:
                if equal:
                    self.socket_type = 'FLOAT'
                else:
                    self.socket_type = 'VECTOR'
                self.node_instance.display_type = self.socket_type
        elif isinstance(value, float) and self.socket_type == 'COLOR':
            # float is better displayed in FLOAT mode; VECTOR is ok too, ignore
            self.socket_type = 'FLOAT'
            self.node_instance.display_type = self.socket_type

        super().set_socket_value(input_socket, value)

    def compile_input_node(self, name, value):
        """ Turn inputs display mode to VECTOR if anything linked to node """
        self.socket_type = 'VECTOR'
        self.node_instance.display_type = self.socket_type

        return super().compile_input_node(name, value)


class LookupCompiler(BasicNodeCompiler):
    """ RPR Lookup node importer """
    lookup_id_to_type = {
        '0': 'UV',
        '1': 'NORMAL',
        '2': 'POS',
        '3': 'INVEC',
        # '4': 'OUTVEC' not supported anymore by core
        '5': 'UV1',
    }

    def compile_input_special(self, input_name: str, value):
        if input_name == 'value':
            enum_id = self.lookup_id_to_type.get(value, None)
            if enum_id:
                self.node_instance.lookup_type = enum_id
                return None

        return None


# map Material Library nodes types to actual node bl_idname and compiler class
node_compilers = {
    'UBER': ('RPRShaderNodeUber', UberMaterialCompiler),
    'BUMP_MAP': ('RPRShaderNodeBumpMap', BumpNormalNodesCompiler),
    'NORMAL_MAP': ('RPRShaderNodeNormalMap', BumpNormalNodesCompiler),
    'IMAGE_TEXTURE': ('RPRShaderNodeImageTexture', ImageTextureCompiler),
    'BLEND': ('RPRShaderNodeBlend', ShaderBlendCompiler),
    'BLEND_VALUE': ('ShaderNodeMixRGB', ValueBlendCompiler),
    'EMISSIVE': ('RPRShaderNodeEmissive', EmissiveCompiler),
    'INPUT_LOOKUP': ('RPRShaderNodeLookup', LookupCompiler),
    'ARITHMETIC': ('RPRValueNode_Math', RPRMathCompiler),
}
