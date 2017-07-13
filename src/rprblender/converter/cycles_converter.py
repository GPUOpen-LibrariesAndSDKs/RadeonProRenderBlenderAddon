import traceback

import rprblender
import rprblender.material_editor
from rprblender.node_editor import find_node
from rprblender.converter.converter import log_convert

from rprblender.converter import converter


class CyclesMaterialConverter(converter.MaterialConverter):
    def __init__(self):
        self.cleanup_other_nodes = False  # remove non RPR nodes
        self.error = False
        self.errors = []

    def error_convert(self, category, name, *args):
        converter.error_convert('category:', category, "<%s>" % name, *args)
        self.error = True
        self.errors.append(' '.join(str(arg) for arg in args))

    def convert(self, material):
        assert material
        log_convert('try to convert material: ', material.name)
        self.material = material

        if not material.node_tree:
            self.error_convert('generic', "material '%s' hasn't node tree, skip conversion" % material)
            return

        self.source_output = find_node(material, 'ShaderNodeOutputMaterial')
        if not self.source_output:
            self.error_convert('generic', "material '%s' hasn't output Cycles node, skip conversion" % material)
            return

        self.tree = material.node_tree
        self.material_editor = rprblender.material_editor.MaterialEditor(self.tree)
        self.cleanup_rpr_materials()
        self.calculate_node_graph_bound()
        self.create_rpr_output_node()

        surface = None
        volume = None

        if self.source_output.inputs['Surface'].is_linked:
            cycles_socket_surface = self.source_output.inputs['Surface'].links[0].from_socket
            converted = self.convert_by_socket(cycles_socket_surface)

            if converted:
                if tuple == type(converted):
                    surface, volume = converted
                else:
                    surface = converted
                    volume = None

        if self.source_output.inputs['Volume'].is_linked:
            cycles_socket_volume = self.source_output.inputs['Volume'].links[0].from_socket
            converted = self.convert_by_socket(cycles_socket_volume)
            if type(converted) is tuple and converted[1]:
                assert not volume
                volume = converted[1]

        if self.source_output.inputs['Displacement'].is_linked:
            self.error_convert('unsupported', 'Displacement', "on material '%s'" % material)

        if surface:
            input_socket = self.output_node.get_input_socket(self.output_node.node.shader_in)
            surface.link_to(input_socket)

        if volume:
            input_socket = self.output_node.get_input_socket(self.output_node.node.volume_in)
            volume.link_to(input_socket)

    def get_socket(self, node, socket_name, socket_index=-1):
        if socket_index != -1:
            if socket_index < 0 or socket_index >= len(node.inputs):
                return None
            socket = node.inputs[socket_index]
        else:
            if socket_name not in node.inputs:
                return None
            socket = node.inputs[socket_name]

        return socket

    def get_linked_socket(self, node, value_name, value_index=-1):
        socket = self.get_socket(node, value_name, value_index)
        if socket.is_linked and len(socket.links) > 0:
            return socket.links[0].from_socket
        return None

    def convert_value(self, node, value_name, rpr_node, rpr_value_name):
        socket = self.get_socket(node, value_name)
        self.convert_value_from_socket(socket, rpr_node, rpr_value_name)

    def convert_node_from_socket(self, socket, input):
        if socket.is_linked and len(socket.links) > 0:
            linked_socket = socket.links[0].from_socket
            rpr_linked_node = self.convert_by_socket(linked_socket)
            if rpr_linked_node:
                rpr_linked_node.link_to(input)
            return True

    def convert_value_from_socket(self, socket, rpr_node, rpr_value_name, value_converter=None):
        input = rpr_node.node.inputs[rpr_value_name]
        if socket.is_linked and len(socket.links) > 0:
            linked_socket = socket.links[0].from_socket
            rpr_linked_node = self.convert_by_socket(linked_socket)
            if rpr_linked_node:
                rpr_linked_node.link_to(input)
        else:
            log_convert('socket.default_value: ', socket.default_value)
            value = value_converter(socket.default_value) if value_converter else socket.default_value
            input.default_value = value

    def convert_value_from_socket_reusable_node(self, socket, value_type, value_converter=None):
        if socket.is_linked and len(socket.links) > 0:
            linked_socket = socket.links[0].from_socket
            return self.convert_by_socket(linked_socket)
        else:
            value = value_converter(socket.default_value) if value_converter else socket.default_value
            if 'color' == value_type:
                value_node = self.material_editor.create_input_constant_node()
                value_node.node.color = value
            else:
                value_node = self.material_editor.create_input_value_node()
                value_node.node.type = value_type
                if 'vector' == value_type:
                    value_node.node.value_vector4 = value
                else:
                    value_node.node.value_float = value
            value_node.node.location = (self.last_node_location[0] - 200, self.last_node_location[1])
            return value_node

    @staticmethod
    def float_to_vec4(v):
        return (v, v, v, 0.0)

    @staticmethod
    def vec3_to_vec4(v):
        return (v[0], v[1], v[2], 0.0)

    def convert_node_diffuse(self, params):
        cycles_node = params.node
        diffuse = self.material_editor.create_diffuse_material_node()
        diffuse.node.location = self.get_new_loacation(cycles_node)
        self.convert_value(cycles_node, 'Color', diffuse, diffuse.node.color_in)
        self.convert_value(cycles_node, 'Roughness', diffuse, diffuse.node.roughness_in)
        socket_normal = self.get_socket(cycles_node, 'Normal')
        self.convert_value_from_socket(socket_normal, diffuse, diffuse.node.normal_in, self.vec3_to_vec4)
        return diffuse

    def convert_node_emission(self, params):
        cycles_node = params.node
        emissive = self.material_editor.create_emissive_material_node()
        emissive.node.location = self.get_new_loacation(cycles_node)
        self.convert_value(cycles_node, 'Color', emissive, emissive.node.color_in)
        self.convert_value(cycles_node, 'Strength', emissive, emissive.node.intensity_in)
        return emissive

    def convert_node_rgb(self, params):
        cycles_node = params.node
        color = self.material_editor.create_input_constant_node()
        color.node.location = self.get_new_loacation(cycles_node)
        color_value = cycles_node.outputs['Color'].default_value
        color.node.color = color_value
        return color

    def convert_node_mix_shader(self, params):
        cycles_node = params.node
        blend = self.material_editor.create_blend_material_node()
        blend.node.location = self.get_new_loacation(cycles_node)

        if cycles_node.bl_idname == 'ShaderNodeAddShader':
            blend.set_input_socket_value_by_name('weight', 0.5)
            index1 = 0
            index2 = 1
        else:
            self.convert_value(cycles_node, 'Fac', blend, blend.node.weight_in)
            index1 = 1
            index2 = 2

        cycles_socket1 = self.get_linked_socket(cycles_node, None, index1)
        cycles_socket2 = self.get_linked_socket(cycles_node, None, index2)

        if cycles_socket1 is not None:
            shader1 = self.convert_by_socket(cycles_socket1)
            input1 = blend.get_input_socket(blend.node.shader1_in)
            self.material_editor.link_nodes(shader1, input1)

        if cycles_socket2 is not None:
            shader2 = self.convert_by_socket(cycles_socket2)
            input2 = blend.get_input_socket(blend.node.shader2_in)
            self.material_editor.link_nodes(shader2, input2)

        return blend

    def convert_node_transparent(self, params):
        cycles_node = params.node
        transparent = self.material_editor.create_transparent_material_node()
        transparent.node.location = self.get_new_loacation(cycles_node)
        self.convert_value(cycles_node, 'Color', transparent, transparent.node.color_in)
        return transparent

    def convert_node_glass(self, params):
        cycles_node = params.node

        frame = self.tree.nodes.new(type='NodeFrame')
        frame.label = 'Glass'

        nodes = []
        blend = self.material_editor.create_blend_material_node()

        nodes.append(blend)

        refraction = self.material_editor.create_microfacet_refraction_material_node()
        nodes.append(refraction)
        refraction.node.location = (blend.node.location[0] - 200, blend.node.location[1] - 100)
        reflection = self.material_editor.create_microfacet_material_node()
        nodes.append(reflection)
        reflection.node.location = (blend.node.location[0] - 200, blend.node.location[1])
        fresnel = self.material_editor.create_fresnel_node()
        nodes.append(fresnel)
        fresnel.node.location = (blend.node.location[0] - 200, blend.node.location[1] + 100)

        self.material_editor.link_nodes(fresnel, blend.get_input_socket(blend.node.weight_in))
        self.material_editor.link_nodes(refraction, blend.get_input_socket(blend.node.shader1_in))
        self.material_editor.link_nodes(reflection, blend.get_input_socket(blend.node.shader2_in))

        for node in nodes:
            node.node.parent = frame

        frame.location = self.get_new_loacation(cycles_node, 250)
        self.get_new_loacation(cycles_node, 200)

        ior_node = self.convert_value_from_socket_reusable_node(cycles_node.inputs['IOR'], 'float')
        roughness_node = self.convert_value_from_socket_reusable_node(cycles_node.inputs['Roughness'], 'float')
        color_node = self.convert_value_from_socket_reusable_node(cycles_node.inputs['Color'], 'color')

        socket = cycles_node.inputs['Normal']
        rpr_linked_node = None
        if socket.is_linked and len(socket.links) > 0:
            linked_socket = socket.links[0].from_socket
            rpr_linked_node = self.convert_by_socket(linked_socket)
        normal_node = rpr_linked_node

        self.material_editor.link_nodes(ior_node, fresnel.get_input_socket_by_name('ior'))
        self.material_editor.link_nodes(ior_node, refraction.get_input_socket_by_name('ior'))

        self.material_editor.link_nodes(roughness_node, refraction.get_input_socket_by_name('roughness'))
        self.material_editor.link_nodes(roughness_node, reflection.get_input_socket_by_name('roughness'))

        self.material_editor.link_nodes(color_node, refraction.get_input_socket_by_name('color'))
        self.material_editor.link_nodes(color_node, reflection.get_input_socket_by_name('color'))

        if normal_node:
            self.material_editor.link_nodes(normal_node, fresnel.get_input_socket_by_name('normal'))
            self.material_editor.link_nodes(normal_node, refraction.get_input_socket_by_name('normal'))
            self.material_editor.link_nodes(normal_node, reflection.get_input_socket_by_name('normal'))

        # self.convert_value(cycles_node, 'Color', blend, blend.node.color_in)
        return blend

    def convert_node_refraction(self, params):
        cycles_node = params.node

        refraction = self.material_editor.create_microfacet_refraction_material_node()
        refraction.node.location = self.get_new_loacation(cycles_node)

        self.convert_value_from_socket(cycles_node.inputs['Roughness'], refraction, refraction.node.roughness_in)
        self.convert_value_from_socket(cycles_node.inputs['Color'], refraction, refraction.node.color_in)

        self.convert_node_from_socket(cycles_node.inputs['Normal'], refraction.node.inputs[refraction.node.normal_in])
        self.convert_value_from_socket(cycles_node.inputs['IOR'], refraction, refraction.node.ior_in)

        return refraction

    def convert_node_reflection(self, params):
        cycles_node = params.node

        result = self.material_editor.create_microfacet_material_node()
        result.node.location = self.get_new_loacation(cycles_node)

        self.convert_value_from_socket(cycles_node.inputs['Roughness'], result, result.node.roughness_in)
        self.convert_value_from_socket(cycles_node.inputs['Color'], result, result.node.color_in)
        self.convert_node_from_socket(cycles_node.inputs['Normal'], result.node.inputs[result.node.normal_in])

        return result

    def convert_node_subsurface_scattering(self, params):
        cycles_node = params.node
        sss = self.material_editor.create_subsurface_material_node()
        sss.node.location = self.get_new_loacation(cycles_node)

        self.convert_value_from_socket(cycles_node.inputs['Color'], sss, sss.node.subsurface_color_in)

        invert_radius = self.material_editor.create_math_node()
        invert_radius.op = 'SUB'
        invert_radius.set_operand_value(0, (1,) * 4)
        cycles_radius = self.convert_value_from_socket_reusable_node(cycles_node.inputs['Radius'], 'vector',
                                                                     value_converter=self.vec3_to_vec4)
        self.material_editor.link_nodes(cycles_radius, invert_radius.get_input_operand_socket(1))
        self.material_editor.link_nodes(invert_radius, sss.get_input_socket_by_name('scatter_color'))

        return None, sss

    def convert_node_volume_scatter(self, params):
        cycles_node = params.node
        volume = self.material_editor.create_volume_material_node()
        volume.node.location = self.get_new_loacation(cycles_node)

        self.convert_value_from_socket(cycles_node.inputs['Color'], volume, volume.node.scatter_color_in)
        self.convert_value_from_socket(cycles_node.inputs['Density'], volume, volume.node.density_in)
        self.convert_value_from_socket(cycles_node.inputs['Anisotropy'], volume, volume.node.scattering_direction_in)

        volume.set_input_socket_value_by_name('transmission_color', (1, 1, 1, 1))
        volume.set_input_socket_value_by_name('emission_color', (0, 0, 0, 1))
        return None, volume

    def convert_node_volume_absorption(self, params):
        cycles_node = params.node
        volume = self.material_editor.create_volume_material_node()
        volume.node.location = self.get_new_loacation(cycles_node)

        self.convert_value_from_socket(cycles_node.inputs['Color'], volume, volume.node.transmission_color_in)
        self.convert_value_from_socket(cycles_node.inputs['Density'], volume, volume.node.density_in)

        volume.set_input_socket_value_by_name('scatter_color', (0, 0, 0, 1))
        volume.set_input_socket_value_by_name('emission_color', (0, 0, 0, 1))
        return None, volume

    def convert_node_vector_math(self, params):
        cycles_node = params.node
        math = self.material_editor.create_math_node()
        math.node.location = self.get_new_loacation(cycles_node)
        math.node.type = 'vector'

        op = None
        if cycles_node.operation == 'ADD':
            op = 'ADD'
        elif cycles_node.operation == 'SUBTRACT':
            op = 'SUB'
        elif cycles_node.operation == 'NORMALIZE':
            single_socket = True
            op = 'NORMALIZE3'
        elif cycles_node.operation == 'CROSS_PRODUCT':
            op = 'CROSS3'
        elif cycles_node.operation == 'DOT_PRODUCT':
            op = 'DOT3'
        elif cycles_node.operation == 'AVERAGE':
            op = 'AVERAGE'
        else:
            self.error_convert('unsupported', "VectorMath " + cycles_node.operation,
                               "operator '%s' not implemented" % cycles_node.operation)
            op = 'ADD'

        if op == None:
            return None
        if op not in math.node.op_settings:
            return None

        math.node.op = op
        op_desc = math.node.op_settings[op]
        params = op_desc['params']
        socket1 = self.get_socket(cycles_node, None, 0)
        self.convert_value_from_socket(socket1, math, params[0][0], self.vec3_to_vec4)
        if len(params) > 1:
            socket2 = self.get_socket(cycles_node, None, 1)
            self.convert_value_from_socket(socket2, math, params[1][0], self.vec3_to_vec4)
        return math

    def convert_node_tex_checker(self, params):
        cycles_node = params.node
        checker_node = self.material_editor.create_checker_node()

        frame = self.tree.nodes.new(type='NodeFrame')
        frame.label = 'Checker'
        nodes = []

        if 'Fac' == params.socket.name:
            checker_node.node.location = self.get_new_loacation(cycles_node)
            nodes.append(checker_node)
            result = checker_node
        else:
            blend_value_node = self.material_editor.create_blend_value_node()
            nodes.append(blend_value_node)

            blend_value_node.node.location = self.get_new_loacation(cycles_node)
            checker_node.node.location = self.get_new_loacation(cycles_node, 180)

            self.material_editor.link_nodes(
                checker_node, blend_value_node.get_input_socket(blend_value_node.node.weight_in))

            self.convert_value_from_socket(cycles_node.inputs['Color1'],
                                           blend_value_node, blend_value_node.node.value1_in)
            self.convert_value_from_socket(cycles_node.inputs['Color2'],
                                           blend_value_node, blend_value_node.node.value2_in)
            result = blend_value_node

        cyces_scale_socket = cycles_node.inputs['Scale']
        cyces_vector_socket = cycles_node.inputs['Vector']

        assert not cyces_scale_socket.is_linked, "only simple scale(number) is supported"

        self.get_new_loacation(cycles_node, 240)

        if cyces_vector_socket.is_linked:
            scale = self.material_editor.create_math_node()
            nodes.append(scale)
            scale.node.location = (checker_node.node.location[0] - 200, checker_node.node.location[1])

            scale.op = 'MUL'
            scale.node.type = 'float'
            scale.set_operand_value(1, (cyces_scale_socket.default_value / 8,) * 4)

            self.convert_node_from_socket(cyces_vector_socket,
                                          scale.get_input_operand_socket(0))

            self.material_editor.link_nodes(scale, checker_node.get_input_socket(checker_node.node.mapping_in))
        else:
            if 8 != cyces_scale_socket.default_value:
                mapping = self.material_editor.create_mapping_node()
                nodes.append(mapping)
                mapping.node.parent = frame
                mapping.node.location = (checker_node.node.location[0] - 200, checker_node.node.location[1] - 100)

                self.material_editor.link_nodes(mapping, checker_node.get_input_socket(checker_node.node.mapping_in))

                mapping.get_input_socket(mapping.node.scale_in).default_value = (
                                                                                cyces_scale_socket.default_value / 8,) * 2
        for node in nodes:
            node.node.parent = frame

        return result

    def convert_node_tex_noise(self, params):
        cycles_node = params.node
        noise_node = self.material_editor.create_noise2d_node()

        if 'Fac' != params.socket.name:
            self.error_convert('unsupported', 'Noise %s output' % params.socket.name,
                               "only Fac output of noise is supported")

        noise_node.node.location = self.get_new_loacation(cycles_node)
        result = noise_node

        cyces_scale_socket = cycles_node.inputs['Scale']
        if cyces_scale_socket.is_linked or 1 != cyces_scale_socket.default_value:
            mapping = self.material_editor.create_mapping_node()
            mapping.node.location = self.get_new_loacation(cycles_node, 240)
            mapping.node.location = (mapping.node.location[0], mapping.node.location[1] - 100)

            self.material_editor.link_nodes(mapping, noise_node.get_input_socket(noise_node.node.mapping_in))

            mapping.get_input_socket(mapping.node.scale_in).default_value = \
                (cyces_scale_socket.default_value / 4,) * 2

        return result

    def convert_node_tex_image(self, params):
        cycles_node = params.node
        image_node = self.material_editor.create_image_texture_node()
        image_node.set_image(cycles_node.image)

        if 'Color' == params.socket.name:
            image_node.node.location = self.get_new_loacation(cycles_node, 50)

            socket = self.get_socket(cycles_node, 'Vector')
            self.convert_value_from_socket(socket, image_node, image_node.node.mapping_in, self.vec3_to_vec4)
            return image_node

        socket = self.get_socket(cycles_node, 'Vector')
        self.convert_value_from_socket(socket, image_node, image_node.node.mapping_in, self.vec3_to_vec4)

        math_node = self.material_editor.create_math_node()
        math_node.node.location = self.get_new_loacation(cycles_node)

        image_node.node.location = self.get_new_loacation(cycles_node, 250)

        math_node.op = 'SELECT_W'
        self.material_editor.link_nodes(image_node, math_node.get_input_operand_socket(0))

        return math_node

    def convert_node_normalmap(self, params):
        cycles_node = params.node
        normalmap_node = self.material_editor.create_normalmap_node()
        normalmap_node.node.location = self.get_new_loacation(cycles_node)

        self.convert_value_from_socket(self.get_socket(cycles_node, 'Strength'),
                                       normalmap_node, normalmap_node.node.scale_in)

        cycles_color_socket = self.get_linked_socket(cycles_node, value_name='Color')

        self.convert_value_from_socket(cycles_color_socket,
                                       normalmap_node, normalmap_node.node.map_in)

        return normalmap_node

    def convert_node_bump(self, params):
        cycles_node = params.node
        bumpmap_node = self.material_editor.create_bumpmap_node()
        bumpmap_node.node.location = self.get_new_loacation(cycles_node)

        cycles_strength_socket = self.get_socket(cycles_node, 'Strength')
        cycles_distance_socket = self.get_socket(cycles_node, 'Distance')

        # we support only simple Strenght/Distance for simplicity
        if cycles_strength_socket.is_linked:
            self.error_convert('unsupported', "Bump Strength Linked",
                               "unsupported procedural input for Strength")

        if cycles_distance_socket.is_linked:
            self.error_convert('unsupported', "Bump Distance Linked",
                               "unsupported procedural input for Distance")

        bumpmap_node.node.inputs[bumpmap_node.node.scale_in].default_value = (
            10 * cycles_strength_socket.default_value * cycles_distance_socket.default_value
        )

        self.convert_node_from_socket(cycles_node.inputs['Height'],
                                      bumpmap_node.get_input_socket_by_name('map'))

        return bumpmap_node

    def convert_node_separate_rgb(self, params):
        if params.socket.name == 'R':
            op = 'SELECT_X'
        elif params.socket.name == 'G':
            op = 'SELECT_Y'
        elif params.socket.name == 'B':
            op = 'SELECT_Z'
        else:
            assert False, ("unknown socket '%s'" % params.socket.name)

        cycles_node = params.node
        math = self.material_editor.create_math_node()
        math.node.location = self.get_new_loacation(cycles_node)
        math.node.type = 'color'
        math.node.op = op
        op_desc = math.node.op_settings[math.node.op]
        params = op_desc['params']
        self.convert_value(cycles_node, 'Image', math, params[0][0])
        return math

    def convert_node_separate_xyz(self, params):
        if params.socket.name == 'X':
            op = 'SELECT_X'
        elif params.socket.name == 'Y':
            op = 'SELECT_Y'
        elif params.socket.name == 'Z':
            op = 'SELECT_Z'
        else:
            assert False, ("unknown socket '%s'" % params.socket.name)

        cycles_node = params.node
        math = self.material_editor.create_math_node()
        math.node.location = self.get_new_loacation(cycles_node)
        math.node.type = 'vector'
        math.node.op = op
        op_desc = math.node.op_settings[math.node.op]
        params = op_desc['params']
        socket = self.get_socket(cycles_node, 'Vector')
        self.convert_value_from_socket(socket, math, params[0][0], self.vec3_to_vec4)
        return math

    def convert_node_math(self, params):
        cycles_node = params.node
        log_convert('  operation: ', cycles_node.operation)
        log_convert('  use_clamp: ', cycles_node.use_clamp)

        op = None
        if cycles_node.operation == 'ADD':
            op = 'ADD'
        elif cycles_node.operation == 'SUBTRACT':
            op = 'SUB'
        elif cycles_node.operation == 'MULTIPLY':
            op = 'MUL'
        elif cycles_node.operation == 'DIVIDE':
            op = 'DIV'
        elif cycles_node.operation == 'SINE':
            op = 'SIN'
        elif cycles_node.operation == 'COSINE':
            op = 'COS'
        elif cycles_node.operation == 'TANGENT':
            op = 'TAN'
        elif cycles_node.operation == 'ARCSINE':
            op = 'ASIN'
        elif cycles_node.operation == 'ARCCOSINE':
            op = 'ACOS'
        elif cycles_node.operation == 'ARCTANGENT':
            op = 'ATAN'
        elif cycles_node.operation == 'POWER':
            op = 'POW'
        elif cycles_node.operation == 'MODULO':
            op = 'MOD'
        elif cycles_node.operation == 'ABSOLUTE':
            op = 'ABS'
        elif cycles_node.operation == 'MINIMUM':
            op = 'MIN'
        elif cycles_node.operation == 'MAXIMUM':
            op = 'MAX'
        elif cycles_node.operation == 'ROUND':
            return self.convert_node_math_round(params)
        else:
            self.error_convert('unsupported', 'Math ' + cycles_node.operation,
                               "operator '%s' not implemented" % cycles_node.operation)
            op = 'ADD'

        # elif cycles_node.operation == 'LOGARITHM':
        #     op = ''
        # elif cycles_node.operation == 'LESS_THAN':
        #     op = ''
        # elif cycles_node.operation == 'GREATER_THAN':
        #     op = ''

        math = self.material_editor.create_math_node()
        math.node.location = self.get_new_loacation(cycles_node)
        math.node.type = 'float'
        if op == None or op not in math.node.op_settings:
            return None

        math.node.use_clamp = cycles_node.use_clamp

        math.node.op = op
        op_desc = math.node.op_settings[op]
        params = op_desc['params']

        socket1 = self.get_socket(cycles_node, None, 0)
        self.convert_value_from_socket(socket1, math, params[0][0], self.float_to_vec4)

        if len(params) > 1:
            socket2 = self.get_socket(cycles_node, None, 1)
            self.convert_value_from_socket(socket2, math, params[1][0], self.float_to_vec4)
        return math

    def convert_node_math_round(self, params):
        cycles_node = params.node

        math = self.material_editor.create_math_node()
        math.node.location = self.get_new_loacation(cycles_node)
        math.node.type = 'float'
        math.node.op = 'FLOOR'

        math.node.use_clamp = cycles_node.use_clamp

        op_desc = math.node.op_settings[math.node.op]
        params = op_desc['params']

        math_add = self.material_editor.create_math_node()
        math_add.node.location = self.get_new_loacation(cycles_node, 180)
        math_add.node.type = 'float'
        math_add.node.op = 'ADD'

        op_desc_add = math_add.node.op_settings[math_add.node.op]
        params_add = op_desc_add['params']

        input_socket = math.get_input_socket(params[0][0])
        math_add.link_to(input_socket)

        socket_val = self.get_socket(cycles_node, None, 0)
        self.convert_value_from_socket(socket_val, math_add, params_add[0][0], self.float_to_vec4)

        socket_add_const = math_add.get_input_socket(params_add[1][0])
        socket_add_const.default_value = (0.5, 0.5, 0.5, 0.5)

        return math

    def convert_node_mix_rgb(self, params):
        cycles_node = params.node
        blend = self.material_editor.create_blend_value_node()
        blend.node.location = self.get_new_loacation(cycles_node)
        self.convert_value(cycles_node, 'Fac', blend, blend.node.weight_in)
        self.convert_value(cycles_node, 'Color1', blend, blend.node.value1_in)
        self.convert_value(cycles_node, 'Color2', blend, blend.node.value2_in)
        if cycles_node.blend_type != 'MIX':
            self.error_convert('unsupported', "Mix " + cycles_node.blend_type,
                               "blend_type '%s' not supported" % cycles_node.blend_type)
        return blend

    def convert_node_combine_xyz(self, params):
        cycles_node = params.node
        math = self.material_editor.create_math_node()
        math.node.location = self.get_new_loacation(cycles_node)
        math.node.type = 'float'
        math.node.op = 'COMBINE'
        op_desc = math.node.op_settings[math.node.op]
        params = op_desc['params']
        for i in range(3):
            socket = self.get_socket(cycles_node, None, i)
            self.convert_value_from_socket(socket, math, params[i][0], self.float_to_vec4)

        return math

    def convert_node_value(self, params):
        cycles_node = params.node
        value = self.material_editor.create_value_node()
        value.node.location = self.get_new_loacation(cycles_node)
        value.node.type = 'float'
        value.node.value_float = cycles_node.outputs['Value'].default_value
        return value

    def convert_node_fresnel(self, params):
        cycles_node = params.node
        fresnel = self.material_editor.create_fresnel_node()
        fresnel.node.location = self.get_new_loacation(cycles_node)
        self.convert_value(cycles_node, 'IOR', fresnel, fresnel.node.ior_in)
        socket_normal = self.get_socket(cycles_node, 'Normal')
        self.convert_value_from_socket(socket_normal, fresnel, fresnel.node.normal_in, self.vec3_to_vec4)
        return fresnel

    def convert_node_tex_coord(self, params):
        if params.socket.name == 'UV':
            op = 'UV'
        elif params.socket.name == 'Normal':
            op = 'N'
        else:
            self.error_convert('unsupported', 'TextureCoordinate ' + params.socket.name,
                               "texture coordinate '%s' not supported" % params.socket.name)
            op = 'UV'

        cycles_node = params.node
        lookup = self.material_editor.create_input_lookup_node()
        lookup.node.location = self.get_new_loacation(cycles_node)
        lookup.node.type = op
        return lookup

    def convert_node_new_geometry(self, params):
        cycles_node = params.node
        if params.socket.name == 'Normal':
            op = 'N'
        elif params.socket.name == 'Position':
            math = self.material_editor.create_math_node()
            math.node.location = self.get_new_loacation(cycles_node)
            math.node.type = 'float'
            math.node.op = 'MUL'

            lookup = self.material_editor.create_input_lookup_node()
            lookup.node.location = self.get_new_loacation(cycles_node, 200)
            lookup.node.type = 'P'

            op_desc = math.node.op_settings[math.node.op]
            params = op_desc['params']

            socket_value1 = math.get_input_socket(params[0][0])
            lookup.link_to(socket_value1)

            socket_value2 = math.get_input_socket(params[1][0])
            socket_value2.default_value = (100, 100, 100, 100)  # why?
            return math
        elif params.socket.name == 'Incoming':
            math = self.material_editor.create_math_node()
            math.node.location = self.get_new_loacation(cycles_node)
            math.node.type = 'float'
            math.node.op = 'MUL'

            lookup = self.material_editor.create_input_lookup_node()
            lookup.node.location = self.get_new_loacation(cycles_node, 200)
            lookup.node.type = 'INVEC'

            op_desc = math.node.op_settings[math.node.op]
            params = op_desc['params']

            socket_value1 = math.get_input_socket(params[0][0])
            lookup.link_to(socket_value1)

            socket_value2 = math.get_input_socket(params[1][0])
            socket_value2.default_value = (-1, -1, -1, -1)
            return math

        else:
            self.error_convert('unsupported', 'Geometry ' + params.socket.name,
                               "texture coordinate '%s' not supported" % params.socket.name)
            op = 'UV'

        lookup = self.material_editor.create_input_lookup_node()
        lookup.node.location = self.get_new_loacation(cycles_node)
        lookup.node.type = op
        return lookup

    def convert_node_translucent(self, params):
        cycles_node = params.node
        diffuse_refraction = self.material_editor.create_diffuse_refraction_material_node()
        diffuse_refraction.node.location = self.get_new_loacation(cycles_node, 10)
        self.convert_value(cycles_node, 'Color', diffuse_refraction, diffuse_refraction.node.color_in)
        socket_normal = self.get_socket(cycles_node, 'Normal')
        self.convert_value_from_socket(socket_normal, diffuse_refraction, diffuse_refraction.node.normal_in,
                                       self.vec3_to_vec4)
        return diffuse_refraction

    def convert_node_rgbcurve(self, params):
        cycles_node = params.node
        self.error_convert('unsupported', cycles_node.bl_idname,
                           "node '%s' conversion not implemented!" % cycles_node.bl_idname)
        math = self.material_editor.create_math_node()
        math.node.type = 'color'
        math.node.op = 'ADD'
        math.node.location = self.get_new_loacation(cycles_node)
        self.convert_value(cycles_node, 'Color', math, 'Value 1')
        math.node.inputs['Value 2'].default_value = (0, 0, 0, 0)
        return math

    def convert_node_mapping(self, params):
        cycles_node = params.node

        has_scale = cycles_node.scale[0] != 1.0 or cycles_node.scale[1] != 1.0 or cycles_node.scale[2] != 1.0
        has_translation = cycles_node.translation[0] != 0.0 or cycles_node.translation[1] != 0.0 or \
                          cycles_node.translation[2] != 0.0
        has_rotation = cycles_node.rotation[0] != 0.0 or cycles_node.rotation[1] != 0.0 or \
                       cycles_node.rotation[2] != 0.0

        if has_rotation:
            self.error_convert('unsupported', 'Mapping Rotation',
                               "node_mapping '%s' conversion not support rotation" % cycles_node.bl_idname)

        result_node = None

        math_scale = None
        math_translation = None
        math_max = None
        math_min = None
        math_normalize = None
        last_node = None

        if has_scale:
            math_scale = self.material_editor.create_math_node()
            math_scale.node.type = 'vector'
            math_scale.node.op = 'MUL'

            op_desc = math_scale.node.op_settings[math_scale.node.op]
            scale_params = op_desc['params']

            last_node = math_scale
            socket_value2 = math_scale.get_input_socket(scale_params[1][0])

            if cycles_node.vector_type in ['TEXTURE', 'NORMAL']:
                socket_value2.default_value = (1 / cycles_node.scale[0] if cycles_node.scale[0] != 0 else 0,
                                               1 / cycles_node.scale[1] if cycles_node.scale[1] != 0 else 0,
                                               1 / cycles_node.scale[2] if cycles_node.scale[2] != 0 else 0,
                                               0)
            else:
                socket_value2.default_value = (cycles_node.scale[0], cycles_node.scale[1], cycles_node.scale[2], 0)

            result_node = math_scale

        if has_translation and cycles_node.vector_type in ['TEXTURE', 'POINT']:
            math_translation = self.material_editor.create_math_node()
            math_translation.node.type = 'vector'
            math_translation.node.op = 'ADD'

            op_desc = math_translation.node.op_settings[math_translation.node.op]
            translation_params = op_desc['params']

            if result_node:
                socket_value1 = math_translation.get_input_socket(translation_params[0][0])
                result_node.link_to(socket_value1)
            else:
                last_node = math_translation

            socket_value2 = math_translation.get_input_socket(translation_params[1][0])
            if cycles_node.vector_type == 'TEXTURE':
                socket_value2.default_value = (
                    -cycles_node.translation[0] / cycles_node.scale[0] if cycles_node.scale[0] != 0 else 0,
                    -cycles_node.translation[1] / cycles_node.scale[1] if cycles_node.scale[1] != 0 else 0,
                    -cycles_node.translation[2] / cycles_node.scale[2] if cycles_node.scale[2] != 0 else 0,
                    0)
            else:
                socket_value2.default_value = (
                cycles_node.translation[0], cycles_node.translation[1], cycles_node.translation[2], 0)
            result_node = math_translation

        if cycles_node.use_min:
            math_max = self.material_editor.create_math_node()
            math_max.node.type = 'vector'
            math_max.node.op = 'MAX'
            op_desc = math_max.node.op_settings[math_max.node.op]
            max_params = op_desc['params']
            if result_node:
                socket_value1 = math_max.get_input_socket(max_params[0][0])
                result_node.link_to(socket_value1)
            socket_value2 = math_max.get_input_socket(max_params[1][0])
            socket_value2.default_value = (cycles_node.min[0], cycles_node.min[1], cycles_node.min[2], 0)
            if not last_node:
                last_node = math_max
            result_node = math_max

        if cycles_node.use_max:
            math_min = self.material_editor.create_math_node()
            math_min.node.type = 'vector'
            math_min.node.op = 'MIN'
            op_desc = math_min.node.op_settings[math_min.node.op]
            min_params = op_desc['params']
            if result_node:
                socket_value1 = math_min.get_input_socket(min_params[0][0])
                result_node.link_to(socket_value1)
            socket_value2 = math_min.get_input_socket(min_params[1][0])
            socket_value2.default_value = (cycles_node.max[0], cycles_node.max[1], cycles_node.max[2], 0)
            if not last_node:
                last_node = math_min
            result_node = math_min

        if cycles_node.vector_type == 'NORMAL':
            math_normalize = self.material_editor.create_math_node()
            math_normalize.node.type = 'vector'
            math_normalize.node.op = 'NORMALIZE3'
            op_desc = math_normalize.node.op_settings[math_normalize.node.op]
            normalize_params = op_desc['params']
            socket_value = math_normalize.get_input_socket(normalize_params[0][0])
            if result_node:
                result_node.link_to(socket_value)
            if not last_node:
                last_node = math_normalize
            result_node = math_normalize

        use_offset = False

        if math_normalize:
            math_normalize.node.location = self.get_new_loacation(cycles_node)
            use_offset = True

        if math_min:
            math_min.node.location = self.get_new_loacation(cycles_node, 180 if use_offset else 0)
            use_offset = True

        if math_max:
            math_max.node.location = self.get_new_loacation(cycles_node, 180 if use_offset else 0)
            use_offset = True

        if math_translation:
            math_translation.node.location = self.get_new_loacation(cycles_node, 180 if use_offset else 0)
            use_offset = True

        if math_scale:
            math_scale.node.location = self.get_new_loacation(cycles_node, 180 if use_offset else 0)

        socket_vector = self.get_socket(cycles_node, 'Vector')
        if socket_vector.is_linked:
            if last_node:
                op_desc = last_node.node.op_settings[last_node.node.op]
                last_node_params = op_desc['params']
                self.convert_value_from_socket(socket_vector, last_node, last_node_params[0][0])
            else:
                cycles_socket_in = socket_vector.links[0].from_socket
                result_node = self.convert_by_socket(cycles_socket_in)
        else:
            value = self.material_editor.create_value_node()
            value.node.location = self.get_new_loacation(cycles_node, 180)
            value.node.type = 'vector'

            if last_node:
                assert last_node.node.bl_idname == 'rpr_arithmetics_node_math'
                value_socket = last_node.node.inputs[0]  # only for math
                value.link_to(value_socket)
            else:
                assert result_node == None
                result_node = value

            value.node.default_value = self.vec3_to_vec4(socket_vector.default_value)

        return result_node

    def convert_by_socket(self, cycles_socket):
        registered_nodes = {
            'ShaderNodeBsdfDiffuse': self.convert_node_diffuse,
            'ShaderNodeEmission': self.convert_node_emission,
            'ShaderNodeRGB': self.convert_node_rgb,
            'ShaderNodeMixShader': self.convert_node_mix_shader,
            'ShaderNodeAddShader': self.convert_node_mix_shader,
            'ShaderNodeBsdfTransparent': self.convert_node_transparent,
            'ShaderNodeVectorMath': self.convert_node_vector_math,
            'ShaderNodeSeparateRGB': self.convert_node_separate_rgb,
            'ShaderNodeSeparateXYZ': self.convert_node_separate_xyz,
            'ShaderNodeTexChecker': self.convert_node_tex_checker,
            'ShaderNodeTexNoise': self.convert_node_tex_noise,
            'ShaderNodeTexImage': self.convert_node_tex_image,
            'ShaderNodeMath': self.convert_node_math,
            'ShaderNodeBsdfGlass': self.convert_node_glass,
            'ShaderNodeNormalMap': self.convert_node_normalmap,
            'ShaderNodeBump': self.convert_node_bump,
            'ShaderNodeMixRGB': self.convert_node_mix_rgb,
            'ShaderNodeBsdfRefraction': self.convert_node_refraction,
            'ShaderNodeBsdfGlossy': self.convert_node_reflection,
            'ShaderNodeCombineRGB': self.convert_node_combine_xyz,
            'ShaderNodeCombineXYZ': self.convert_node_combine_xyz,
            'ShaderNodeValue': self.convert_node_value,
            'ShaderNodeSubsurfaceScattering': self.convert_node_subsurface_scattering,
            'ShaderNodeVolumeScatter': self.convert_node_volume_scatter,
            'ShaderNodeVolumeAbsorption': self.convert_node_volume_absorption,
            'ShaderNodeFresnel': self.convert_node_fresnel,
            'ShaderNodeTexCoord': self.convert_node_tex_coord,
            'ShaderNodeNewGeometry': self.convert_node_new_geometry,
            'ShaderNodeBsdfTranslucent': self.convert_node_translucent,
            'ShaderNodeRGBCurve': self.convert_node_rgbcurve,
            'ShaderNodeMapping': self.convert_node_mapping,
        }

        cycles_node = cycles_socket.node
        name = cycles_node.bl_idname

        class CoverterParams:
            socket = cycles_socket
            node = cycles_node

        self.begin_node_convert(cycles_node)

        res = None
        try:
            if name in registered_nodes:
                log_convert('convert node: ', name)
                try:
                    res = registered_nodes[name](CoverterParams())
                except AssertionError as exc:
                    self.error_convert('generic', "can't convert node '%s'" % name, "from ", self.material,
                                       ", reason: ",
                                       traceback.format_exc())
            else:
                self.error_convert('unsupported', name, " from ", self.material, )
        finally:
            self.end_node_convert(cycles_node)

        return res
