from collections import OrderedDict

import bpy
import sys
from . import nodes
from .nodes import RPRTreeNode, RPRNodeSocketConnectorHelper
from .editor_sockets import RPRSocketValue
from . import rpraddon
from rprblender.core.nodes import log_mat
from . import logging
from bpy_extras.image_utils import load_image
from . import versions
from rprblender.ui import add_subdivision_properties

def fix_path(path):
    if path.startswith('//'):
        res = bpy.path.abspath(path)
    else:
        res = os.path.realpath(path)

    return res.replace('\\', '/')


########################################################################################################################
# Output nodes
########################################################################################################################

@rpraddon.register_class
class RPRShaderNode_Output(RPRTreeNode):
    bl_idname = 'rpr_shader_node_output'
    bl_label = 'RPR Material Output'
    bl_icon = 'MATERIAL'
    bl_width_min = 120

    shader_in = 'Shader'
    volume_in = 'Volume'
    displacement_in = 'Displacement'

    def init(self, context):
        self.inputs.new('NodeSocketShader', self.shader_in)
        self.inputs.new('NodeSocketShader', self.volume_in)
        self.inputs.new('NodeSocketShader', self.displacement_in)


########################################################################################################################
# Shader nodes
########################################################################################################################
class RPRNodeType_Shader(RPRTreeNode):
    shader_out = 'Shader'
    bl_icon = 'MATERIAL'
    def init(self):
        self.outputs.new('NodeSocketShader', self.shader_out)

    def add_socket_if_missed(self, socket_name, socket_type, default_value=None, enabled=None):
        """
        Adds socket if it's missing, in case of loading scene with previous version of Uber2 and Uber3 materials
        """
        if socket_name not in self.inputs:
            log_mat("[{}] Adding '{}' node socket of type '{}'".
                    format(self.bl_idname, socket_name, socket_type))
            self.inputs.new(socket_type, socket_name)
            if default_value is not None:
                self.inputs[socket_name].default_value = default_value
            if enabled is not None:
                self.inputs[socket_name].enabled = enabled


class RPRNodeType_Volume(RPRTreeNode):
    shader_out = 'Volume'
    bl_icon = 'MATERIAL'
    def init(self):
        self.outputs.new('NodeSocketShader', self.shader_out)


@rpraddon.register_class
class RPRShaderNode_Subsurface(RPRNodeType_Volume):
    bl_idname = 'rpr_shader_node_subsurface'
    bl_label = 'RPR Subsurface'
    bl_width_min = 170

    surface_intensity_in = 'Surface Intensity'
    subsurface_color_in = 'Subsurface Color'
    density_in = 'Density'
    scatter_color_in = 'Scatter color'
    scatter_amount_in = 'Scatter Amount'
    emission_color_in = 'Emission Color'
    scattering_direction_in = 'Scattering Direction'
    multiscatter_in = 'Multiscatter'

    def init(self, context):
        super(RPRShaderNode_Subsurface, self).init()
        self.inputs.new('rpr_socket_weight', self.surface_intensity_in)
        self.inputs.new('rpr_socket_color', self.subsurface_color_in)
        self.inputs.new('rpr_socket_color', self.emission_color_in)
        self.inputs.new('rpr_socket_color', self.scatter_color_in)
        self.inputs.new('rpr_socket_factor', self.scatter_amount_in)
        self.inputs.new('rpr_socket_factor', self.density_in)
        self.inputs.new('rpr_socket_scattering_direction', self.scattering_direction_in)
        self.inputs.new('NodeSocketBool', self.multiscatter_in)


@rpraddon.register_class
class RPRShaderNode_Volume(RPRNodeType_Volume):
    bl_idname = 'rpr_shader_node_volume'
    bl_label = 'RPR Volume'
    bl_width_min = 170

    scatter_color_in = 'Scatter color'
    transmission_color_in = 'Transmission color'
    emission_color_in = 'Emission Color'
    density_in = 'Density'
    scattering_direction_in = 'Scattering Direction'
    multiscatter_in = 'Multiscatter'

    def init(self, context):
        super(RPRShaderNode_Volume, self).init()
        self.inputs.new('rpr_socket_color', self.scatter_color_in)
        self.inputs.new('rpr_socket_color', self.transmission_color_in)
        self.inputs.new('rpr_socket_color', self.emission_color_in)
        self.inputs.new('rpr_socket_factor', self.density_in)
        self.inputs.new('rpr_socket_scattering_direction', self.scattering_direction_in)
        self.inputs.new('NodeSocketBool', self.multiscatter_in)


@rpraddon.register_class
class RPRShaderNode_Emissive(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_emissive'
    bl_label = 'RPR Emissive'

    color_in = 'Emissive Color'
    intensity_in = 'Intensity'
    double_sided = bpy.props.BoolProperty(name="Double Sided", default=False)

    def init(self, context):
        super(RPRShaderNode_Emissive, self).init()
        input_emissive_color = self.inputs.new('rpr_socket_color', self.color_in)
        self.inputs.new('rpr_socket_factor', self.intensity_in)
        input_emissive_color.default_value = (1.0, 1.0, 1.0, 1.0)

    def draw_buttons(self, context, layout):
        row = layout.column(align=True)
        row.alignment = 'EXPAND'

        row.prop(self, 'double_sided')


@rpraddon.register_class
class RPRShaderNode_DoubleSided(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_double_sided'
    bl_label = 'RPR Double Sided'

    front_shader = 'Front Shader'
    back_shader = 'Back Shader'
    
    def init(self, context):
        super(RPRShaderNode_DoubleSided, self).init()
        self.inputs.new('NodeSocketShader', self.front_shader)
        self.inputs.new('NodeSocketShader', self.back_shader)


@rpraddon.register_class
class RPRShaderNode_Diffuse(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_diffuse'
    bl_label = 'RPR Diffuse'

    color_in = 'Diffuse Color'
    roughness_in = 'Roughness'
    normal_in = 'Normal'

    def init(self, context):
        super(RPRShaderNode_Diffuse, self).init()
        input_color = self.inputs.new('rpr_socket_color', self.color_in)
        self.inputs.new('rpr_socket_weight', self.roughness_in)
        self.inputs.new('rpr_socket_link', self.normal_in).hide_value=True
        input_color.default_value = (1.0, 1.0, 1.0, 1.0)


@rpraddon.register_class
class RPRShaderNode_FlatColor(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_flat_color'
    bl_label = 'RPR Flat Color'

    color_in = 'Color'

    def init(self, context):
        super(RPRShaderNode_FlatColor, self).init()
        input_color = self.inputs.new('rpr_socket_color', self.color_in)
        input_color.default_value = (1.0, 1.0, 1.0, 1.0)


@rpraddon.register_class
class RPRShaderNode_DiffuseRefraction(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_diffuse_refraction'
    bl_label = 'RPR Diffuse Refraction'

    color_in = 'Diffuse Color'
    normal_in = 'Normal'

    def init(self, context):
        super().init()
        input_color = self.inputs.new('rpr_socket_color', self.color_in)
        self.inputs.new('rpr_socket_link', self.normal_in).hide_value=True
        input_color.default_value = (1.0, 1.0, 1.0, 1.0)


@rpraddon.register_class
class RPRShaderNode_Microfacet(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_microfacet'
    bl_label = 'RPR Microfacet'

    color_in = 'Diffuse Color'
    normal_in = 'Normal'
    roughness_in = 'Roughness'

    def init(self, context):
        super(RPRShaderNode_Microfacet, self).init()
        input_color = self.inputs.new('rpr_socket_color', self.color_in)
        self.inputs.new('rpr_socket_link', self.normal_in).hide_value=True
        self.inputs.new('rpr_socket_weight', self.roughness_in)
        input_color.default_value = (1.0, 1.0, 1.0, 1.0)


@rpraddon.register_class
class RPRShaderNode_MicrofacetRefraction(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_microfacet_refraction'
    bl_label = 'RPR Microfacet Refraction'
    bl_icon = 'MATERIAL'

    color_in = 'Diffuse Color'
    normal_in = 'Normal'
    roughness_in = 'Roughness'
    ior_in = 'IOR'

    def init(self, context):
        super(RPRShaderNode_MicrofacetRefraction, self).init()
        input_color = self.inputs.new('rpr_socket_color', self.color_in)
        self.inputs.new('rpr_socket_link', self.normal_in).hide_value=True
        self.inputs.new('rpr_socket_weight', self.roughness_in)
        self.inputs.new('rpr_socket_ior', self.ior_in)
        input_color.default_value = (1.0, 1.0, 1.0, 1.0)


@rpraddon.register_class
class RPRShaderNode_Blend(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_blend'
    bl_label = 'RPR Shader Blend'

    weight_in = 'Weight'
    shader1_in = 'Shader 1'
    shader2_in = 'Shader 2'

    has_thumbnail = True
    thumbnail = bpy.props.EnumProperty(items=RPRTreeNode.get_thumbnail_enum)

    def init(self, context):
        super(RPRShaderNode_Blend, self).init()
        self.inputs.new('rpr_socket_weight_soft', self.weight_in)
        self.inputs.new('NodeSocketShader', self.shader1_in)
        self.inputs.new('NodeSocketShader', self.shader2_in)

    def draw_buttons(self, context, layout):
        self.draw_thumbnail(layout)


@rpraddon.register_class
class RPRShaderNode_OrenNayar(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_oren_nayar'
    bl_label = 'RPR Oren Nayar'

    color_in = 'Diffuse Color'
    normal_in = 'Normal'
    roughness_in = 'Roughness'

    def init(self, context):
        super(RPRShaderNode_OrenNayar, self).init()
        input_color = self.inputs.new('rpr_socket_color', self.color_in)
        self.inputs.new('rpr_socket_link', self.normal_in).hide_value=True
        self.inputs.new('rpr_socket_weight', self.roughness_in)
        input_color.default_value = (1.0, 1.0, 1.0, 1.0)


@rpraddon.register_class
class RPRShaderNode_Refraction(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_refraction'
    bl_label = 'RPR Refraction'

    color_in = 'Diffuse Color'
    normal_in = 'Normal'
    ior_in = 'IOR'

    def init(self, context):
        super(RPRShaderNode_Refraction, self).init()
        input_color = self.inputs.new('rpr_socket_color', self.color_in)
        self.inputs.new('rpr_socket_link', self.normal_in).hide_value=True
        self.inputs.new('rpr_socket_ior', self.ior_in)
        input_color.default_value = (1.0, 1.0, 1.0, 1.0)


@rpraddon.register_class
class RPRShaderNode_Reflection(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_reflection'
    bl_label = 'RPR Reflection'

    color_in = 'Diffuse Color'
    normal_in = 'Normal'

    def init(self, context):
        super(RPRShaderNode_Reflection, self).init()
        input_color = self.inputs.new('rpr_socket_color', self.color_in)
        self.inputs.new('rpr_socket_link', self.normal_in).hide_value=True
        input_color.default_value = (1.0, 1.0, 1.0, 1.0)


@rpraddon.register_class
class RPRShaderNode_Transparent(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_transparent'
    bl_label = 'RPR Transparent'

    color_in = 'Diffuse Color'

    def init(self, context):
        super(RPRShaderNode_Transparent, self).init()
        input_color = self.inputs.new('rpr_socket_color', self.color_in)
        input_color.default_value = (1.0, 1.0, 1.0, 1.0)


@rpraddon.register_class
class RPRShaderNode_Ward(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_ward'
    bl_label = 'RPR Ward'

    color_in = 'Diffuse Color'
    rotation_in = 'Rotation'
    roughness_x_in = 'Roughness X'
    roughness_y_in = 'Roughness Y'
    normal_in = 'Normal'

    def init(self, context):
        super(RPRShaderNode_Ward, self).init()
        input_color = self.inputs.new('rpr_socket_color', self.color_in)
        self.inputs.new('rpr_socket_angle360', self.rotation_in)
        self.inputs.new('rpr_socket_weight', self.roughness_x_in)
        self.inputs.new('rpr_socket_weight', self.roughness_y_in)
        self.inputs.new('rpr_socket_link', self.normal_in).hide_value=True
        input_color.default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs[self.roughness_x_in].default_value = 0.5
        self.inputs[self.roughness_y_in].default_value = 0.5


@rpraddon.register_class
class OBJECT_OT_Button(bpy.types.Operator):
    bl_idname = "my.button"
    bl_label = "Button"

    def execute(self, context):

        return {'FINISHED'}

@rpraddon.register_class
class RPRShaderNode_Uber(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_uber'
    bl_label = 'RPR Uber (deprecated)'
    bl_width_min = 190

    diffuse_color_in = 'Diffuse Color'
    diffuse_normal_in = 'Diffuse Normal'

    reflect_color_in = 'Reflect Color'
    reflect_ior_in = "Reflect IOR"
    reflect_roughness_x_in = "Reflect Roughness X"
    reflect_roughness_y_in = "Reflect Roughness Y"
    reflect_normal_in = 'Reflect Normal'

    coat_color_in = 'Coat Color'
    coat_ior_in = "Coat IOR"
    coat_normal_in = 'Coat Normal'

    refraction_level_in = 'Refraction Level'
    refraction_color_in = 'Refraction Color'
    refraction_ior_in = "Refraction IOR"
    refraction_roughness_in = "Refraction Roughness"
    refraction_normal_in = 'Refraction Normal'

    transparency_color_in = 'Transparency Color'
    transparency_level_in = "Transparency Level"

    def reflection_change(self, context):
        self.inputs[self.reflect_color_in].enabled = self.reflection
        self.inputs[self.reflect_ior_in].enabled = self.reflection
        self.inputs[self.reflect_roughness_x_in].enabled = self.reflection
        self.inputs[self.reflect_roughness_y_in].enabled = self.reflection
        self.inputs[self.reflect_normal_in].enabled = self.reflection

    def clear_coat_change(self, context):
        self.inputs[self.coat_color_in].enabled = self.clear_coat
        self.inputs[self.coat_ior_in].enabled = self.clear_coat
        self.inputs[self.coat_normal_in].enabled = self.clear_coat
        pass

    def refraction_change(self, context):
        self.inputs[self.refraction_level_in].enabled = self.refraction
        self.inputs[self.refraction_color_in].enabled = self.refraction
        self.inputs[self.refraction_ior_in].enabled = self.refraction
        self.inputs[self.refraction_roughness_in].enabled = self.refraction
        self.inputs[self.refraction_normal_in].enabled = self.refraction
        pass

    reflection = bpy.props.BoolProperty(name='Reflection', update=reflection_change)
    clear_coat = bpy.props.BoolProperty(name='Clear Coat', update=clear_coat_change)
    refraction = bpy.props.BoolProperty(name='Refraction', update=refraction_change)

    def init(self, context):
        super(RPRShaderNode_Uber, self).init()

        self.inputs.new('rpr_socket_color', self.diffuse_color_in).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_color', self.reflect_color_in).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_color', self.coat_color_in).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_color', self.refraction_color_in).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_color', self.transparency_color_in).default_value = (1.0, 1.0, 1.0, 1.0)

        self.inputs.new('rpr_socket_weight', self.transparency_level_in).default_value = 0.0
        self.inputs.new('rpr_socket_weight', self.refraction_level_in)

        self.inputs.new('rpr_socket_link', self.diffuse_normal_in).hide_value=True
        self.inputs.new('rpr_socket_link', self.reflect_normal_in).hide_value=True
        self.inputs.new('rpr_socket_link', self.coat_normal_in).hide_value=True
        self.inputs.new('rpr_socket_link', self.refraction_normal_in).hide_value=True

        self.inputs.new('rpr_socket_ior', self.reflect_ior_in)
        self.inputs.new('rpr_socket_ior', self.coat_ior_in)
        self.inputs.new('rpr_socket_ior', self.refraction_ior_in)

        self.inputs.new('rpr_socket_weight', self.reflect_roughness_x_in)
        self.inputs.new('rpr_socket_weight', self.reflect_roughness_y_in)
        self.inputs.new('rpr_socket_weight', self.refraction_roughness_in)

        self.reflection_change(context)
        self.clear_coat_change(context)
        self.refraction_change(context)

    def draw_buttons(self, context, layout):
        row = layout.column(align=True)
        row.alignment = 'EXPAND'
        row.prop(self, 'reflection', toggle=True)
        row.prop(self, 'clear_coat', toggle=True)
        row.prop(self, 'refraction', toggle=True)


########################################################################################################################
# Uber2 node
########################################################################################################################
# before change - check check_old_rpr_uber2_nodes() please
@rpraddon.register_class
class RPRShaderNode_Uber2(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_uber2'
    bl_label = 'RPR Uber'
    bl_width_min = 300

    diffuse_color = 'Diffuse Color'
    diffuse_weight = 'Diffuse Weight'
    diffuse_roughness = 'Diffuse Roughness'

    reflection_color = 'Reflection Color'
    reflection_weight = 'Reflection Weight'
    reflection_roughness = 'Reflection Roughness'
    reflection_anisotropy = 'Reflection Anisotropy'
    reflection_anisotropy_rotation = 'Reflection Anisotropy Rotation'
    reflection_fresnel_ior = 'Reflection Fresnel IOR'
    reflection_fresnel_metalness = 'Reflection Fresnel Metalness'

    refraction_color = 'Refraction Color'
    refraction_weight = 'Refraction Weight'
    refraction_roughness = 'Refraciton Roughness'
    refraction_ior = 'Refraction IOR'

    coating_color = 'Coating Color'
    coating_weight = 'Coating Weight'
    coating_roughness = 'Coating Roughness'
    coating_fresnel_ior = 'Coating Fresnel IOR'
    
    emissive_color = 'Emissive Color'
    emissive_intensity = 'Emissive Intensity'
    emissive_weight = 'Emissive Weight'

    subsurface_color = 'Subsurface Color'
    subsurface_weight = 'Subsurface Weight'
    subsurface_scatter_color = 'Subsurface Scattering Color'
    subsurface_scatter_direction = 'Subsurface Scattering Direction'
    subsurface_radius = 'Subsurface Radius'
    
    transparency_value = 'Transparency'
    normal_in = 'Normal'
    displacement_map = 'Displacement Map'
    displacement_min = 'Displacement Scale Min'
    displacement_max = 'Displacement Scale Max'

    def diffuse_changed(self, context):
        self.inputs[self.diffuse_color].enabled = self.diffuse
        self.inputs[self.diffuse_weight].enabled = self.diffuse
        self.inputs[self.diffuse_roughness].enabled = self.diffuse

    def reflection_changed(self, context):
        self.inputs[self.reflection_color].enabled = self.reflection
        self.inputs[self.reflection_weight].enabled = self.reflection
        self.inputs[self.reflection_roughness].enabled = self.reflection
        self.inputs[self.reflection_anisotropy].enabled = self.reflection
        self.inputs[self.reflection_anisotropy_rotation].enabled = self.reflection
        self.inputs[self.reflection_fresnel_ior].enabled = self.reflection and not self.reflection_fresnel_metalmaterial
        self.inputs[self.reflection_fresnel_metalness].enabled = self.reflection and self.reflection_fresnel_metalmaterial

    def reflection_fresnel_metalmaterial_changed(self, context):
        self.inputs[self.reflection_fresnel_ior].enabled = not self.reflection_fresnel_metalmaterial
        self.inputs[self.reflection_fresnel_metalness].enabled = self.reflection_fresnel_metalmaterial

    def refraction_changed(self, context):
        self.inputs[self.refraction_color].enabled = self.refraction
        self.inputs[self.refraction_weight].enabled = self.refraction
        self.inputs[self.refraction_roughness].enabled = self.refraction
        self.inputs[self.refraction_ior].enabled = self.refraction

    def coating_changed(self, context):
        self.inputs[self.coating_color].enabled = self.coating
        self.inputs[self.coating_weight].enabled = self.coating
        self.inputs[self.coating_roughness].enabled = self.coating
        self.inputs[self.coating_fresnel_ior].enabled = self.coating

    def emissive_changed(self, context):
        self.inputs[self.emissive_color].enabled = self.emissive
        self.inputs[self.emissive_weight].enabled = self.emissive
        self.inputs[self.emissive_intensity].enabled = self.emissive

    def subsurface_changed(self, context):
        self.inputs[self.subsurface_color].enabled = self.subsurface and not self.subsurface_use_diffuse_color
        self.inputs[self.subsurface_weight].enabled = self.subsurface
        self.inputs[self.subsurface_scatter_color].enabled = self.subsurface
        self.inputs[self.subsurface_scatter_direction].enabled = self.subsurface
        self.inputs[self.subsurface_radius].enabled = self.subsurface

    def subsurface_use_diffuse_color_changed(self, context):
        self.inputs[self.subsurface_color].enabled = not self.subsurface_use_diffuse_color

    def transparency_changed(self, context):
        self.inputs[self.transparency_value].enabled = self.transparency

    def normal_changed(self, context):
        self.inputs[self.normal_in].enabled = self.normal

    def displacement_changed(self, context):
        self.inputs[self.displacement_map].enabled = self.displacement
        self.inputs[self.displacement_min].enabled = self.displacement
        self.inputs[self.displacement_max].enabled = self.displacement

    diffuse = bpy.props.BoolProperty(name='Diffuse', update=diffuse_changed, default=True)

    reflection = bpy.props.BoolProperty(name='Reflection', update=reflection_changed)
    reflection_fresnel_metalmaterial = bpy.props.BoolProperty(name='Reflection Fresnel Metal Material', update=reflection_fresnel_metalmaterial_changed)

    refraction = bpy.props.BoolProperty(name='Refraction', update=refraction_changed)
    refraction_link_to_reflection = bpy.props.BoolProperty(name='Refraction Link to Reflection')
    refraction_thin_surface = bpy.props.BoolProperty(name='Refraction Thin Surface')

    coating = bpy.props.BoolProperty(name='Coating', update=coating_changed)

    emissive = bpy.props.BoolProperty(name='Emissive', update=emissive_changed)
    emissive_double_sided = bpy.props.BoolProperty(name='Emissive Double Sided')

    subsurface = bpy.props.BoolProperty(name='Subsurface', update=subsurface_changed)
    subsurface_use_diffuse_color = bpy.props.BoolProperty(name='Subsurface Use Diffuse Color', update=subsurface_use_diffuse_color_changed)
    subsurface_multiple_scattering = bpy.props.BoolProperty(name='Subsurface Multiple Scattering', default=False)

    transparency = bpy.props.BoolProperty(name='Transparency', update=transparency_changed)
    normal = bpy.props.BoolProperty(name='Normal', update=normal_changed)
    displacement = bpy.props.BoolProperty(name='Displacement', update=displacement_changed)

    def init(self, context):
        super(RPRShaderNode_Uber2, self).init()

        self.inputs.new('rpr_socket_color', self.diffuse_color).default_value = (0.644, 0.644, 0.644, 1.0)
        self.inputs.new('rpr_socket_weight_soft', self.diffuse_weight).default_value = 1.0
        self.inputs.new('rpr_socket_weight', self.diffuse_roughness).default_value = 0.5

        self.inputs.new('rpr_socket_color', self.reflection_color).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_weight_soft', self.reflection_weight).default_value = 1.0
        self.inputs.new('rpr_socket_weight', self.reflection_roughness).default_value = 0.25
        self.inputs.new('rpr_socket_float_MinN1_Max1', self.reflection_anisotropy).default_value = 0.0
        self.inputs.new('rpr_socket_angle360', self.reflection_anisotropy_rotation).default_value = 0.0
        self.inputs.new('rpr_socket_ior', self.reflection_fresnel_ior).default_value = 1.5
        self.inputs.new('rpr_socket_weight', self.reflection_fresnel_metalness).default_value = 1.0

        self.inputs.new('rpr_socket_color', self.refraction_color).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_weight_soft', self.refraction_weight).default_value = 1.0
        self.inputs.new('rpr_socket_weight', self.refraction_roughness).default_value = 0.1
        self.inputs.new('rpr_socket_ior', self.refraction_ior).default_value = 1.5

        self.inputs.new('rpr_socket_color', self.coating_color).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_weight_soft', self.coating_weight).default_value = 1.0
        self.inputs.new('rpr_socket_weight', self.coating_roughness).default_value = 0.01
        self.inputs.new('rpr_socket_ior', self.coating_fresnel_ior).default_value = 1.5

        self.inputs.new('rpr_socket_color', self.emissive_color).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_factor', self.emissive_intensity)
        self.inputs.new('rpr_socket_weight_soft', self.emissive_weight).default_value = 1.0

        self.inputs.new('rpr_socket_color', self.subsurface_color).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_weight_soft', self.subsurface_weight).default_value = 1.0
        self.inputs.new('rpr_socket_color', self.subsurface_scatter_color).default_value = (3.67, 1.37, 0.68, 1.0)  # skin values
        self.inputs.new('rpr_socket_scattering_direction', self.subsurface_scatter_direction).default_value = 0.0
        self.inputs.new('rpr_socket_color', self.subsurface_radius).default_value = (1.0, 1.0, 1.0, 1.0)

        self.inputs.new('rpr_socket_weight', self.transparency_value).default_value = 0.0
        self.inputs.new('rpr_socket_link', self.normal_in)
        self.inputs.new('rpr_socket_color', self.displacement_map).default_value = (0.0, 0.0, 0.0, 1.0)
        self.inputs.new('rpr_socket_float_softMinN1_softMax1', self.displacement_min).default_value = 0.0
        self.inputs.new('rpr_socket_float_softMinN1_softMax1', self.displacement_max).default_value = 1.0

        self.total_update(context)

    def total_update(self, context):
        self.diffuse_changed(context)
        self.reflection_changed(context)
        self.refraction_changed(context)
        self.coating_changed(context)
        self.emissive_changed(context)
        self.subsurface_changed(context)
        self.transparency_changed(context)
        self.normal_changed(context)
        self.displacement_changed(context)

    def draw_buttons(self, context, layout):
        row = layout.column(align=True)
        row.alignment = 'EXPAND'

        row.prop(self, 'diffuse', toggle=True)

        row.prop(self, 'reflection', toggle=True)
        if self.reflection:
            row.prop(self, 'reflection_fresnel_metalmaterial', toggle=False)

        row.prop(self, 'refraction', toggle=True)
        if self.refraction:
            row.prop(self, 'refraction_link_to_reflection', toggle=False)
            row.prop(self, 'refraction_thin_surface', toggle=False)

        row.prop(self, 'coating', toggle=True)
        
        row.prop(self, 'emissive', toggle=True)
        if self.emissive:
            row.prop(self, 'emissive_double_sided', toggle=False)

        row.prop(self, 'subsurface', toggle=True)
        if self.subsurface:
            row.prop(self, 'subsurface_use_diffuse_color', toggle=False)
            row.prop(self, 'subsurface_multiple_scattering', toggle=False)

        row.prop(self, 'transparency', toggle=True)
        row.prop(self, 'normal', toggle=True)
        row.prop(self, 'displacement', toggle=True)
        if self.displacement:
            active_object = bpy.context.active_object
            if active_object is not None:
                from rprblender.ui import add_subdivision_properties
                col = row.column()
                add_subdivision_properties(col, active_object)


########################################################################################################################
# Uber3 node
########################################################################################################################
# before change - check check_old_rpr_uber2_nodes() please
@rpraddon.register_class
class RPRShaderNode_Uber3(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_uber3'
    bl_label = 'RPR Uber'
    bl_width_min = 300

    diffuse_color = 'Diffuse Color'
    diffuse_weight = 'Diffuse Weight'
    diffuse_roughness = 'Diffuse Roughness'
    diffuse_normal = 'Diffuse Normal'

    sheen_color = 'Sheen Color'
    sheen_weight = 'Sheen Weight'
    sheen_tint = 'Sheen Tint'
    
    reflection_color = 'Reflection Color'
    reflection_weight = 'Reflection Weight'
    reflection_roughness = 'Reflection Roughness'
    reflection_anisotropy = 'Reflection Anisotropy'
    reflection_anisotropy_rotation = 'Reflection Anisotropy Rotation'
    reflection_ior = 'Reflection IOR'
    reflection_metalness = 'Reflection Metalness'
    reflection_normal = 'Reflection Normal'

    refraction_color = 'Refraction Color'
    refraction_weight = 'Refraction Weight'
    refraction_roughness = 'Refraction Roughness'
    refraction_ior = 'Refraction IOR'
    refraction_absorption_distance = 'Refraction Absorption Distance'
    refraction_absorption_color = 'Refraction Absorption Color'

    coating_color = 'Coating Color'
    coating_weight = 'Coating Weight'
    coating_roughness = 'Coating Roughness'
    coating_ior = 'Coating IOR'
    coating_normal = 'Coating Normal'
    coating_thickness = 'Coating Thickness'
    coating_transmission_color = 'Coating Transmission Color'
    
    emissive_color = 'Emissive Color'
    emissive_weight = 'Emissive Weight'

    subsurface_weight = 'Subsurface Weight'
    subsurface_scatter_color = 'Subsurface Scattering Color'
    subsurface_scatter_direction = 'Subsurface Scattering Direction'
    subsurface_radius = 'Subsurface Radius'
    
    backscatter_color = 'Backscattering Color'
    backscatter_weight = 'Backscattering Weight'

    normal_in = 'Normal'
    transparency_value = 'Transparency'
    displacement_map = 'Displacement Map'

    def diffuse_changed(self, context):
        self.inputs[self.diffuse_color].enabled = self.diffuse
        self.inputs[self.diffuse_weight].enabled = self.diffuse
        self.inputs[self.diffuse_roughness].enabled = self.diffuse
        self.inputs[self.backscatter_weight].enabled = self.diffuse
        self.diffuse_use_shader_normal_changed(context)
        self.backscatter_separate_color_changed(context)

    def sheen_changed(self, context):
        self.inputs[self.sheen_color].enabled = self.sheen
        self.inputs[self.sheen_weight].enabled = self.sheen
        self.inputs[self.sheen_tint].enabled = self.sheen
    
    def diffuse_use_shader_normal_changed(self, context):
        self.inputs[self.diffuse_normal].enabled = self.diffuse and not self.diffuse_use_shader_normal

    def backscatter_separate_color_changed(self, context):
        self.inputs[self.backscatter_color].enabled = self.diffuse and self.backscatter_separate_color

    def reflection_changed(self, context):
        self.inputs[self.reflection_color].enabled = self.reflection
        self.inputs[self.reflection_weight].enabled = self.reflection
        self.inputs[self.reflection_roughness].enabled = self.reflection
        self.inputs[self.reflection_anisotropy].enabled = self.reflection
        self.inputs[self.reflection_anisotropy_rotation].enabled = self.reflection
        self.reflection_use_shader_normal_changed(context)
        self.reflection_mode_changed(context)

    def reflection_use_shader_normal_changed(self, context):
        self.inputs[self.reflection_normal].enabled = self.reflection and not self.reflection_use_shader_normal

    def reflection_mode_changed(self, context):
        self.inputs[self.reflection_ior].enabled = self.reflection and (self.reflection_mode == 'IOR')
        self.inputs[self.reflection_metalness].enabled = self.reflection and (self.reflection_mode == 'METALNESS')

    def refraction_changed(self, context):
        self.inputs[self.refraction_color].enabled = self.refraction
        self.inputs[self.refraction_weight].enabled = self.refraction
        self.inputs[self.refraction_roughness].enabled = self.refraction
        self.inputs[self.refraction_ior].enabled = self.refraction
        self.inputs[self.refraction_absorption_distance].enabled = self.refraction
        self.inputs[self.refraction_absorption_color].enabled = self.refraction

    def coating_changed(self, context):
        self.inputs[self.coating_color].enabled = self.coating
        self.inputs[self.coating_weight].enabled = self.coating
        self.inputs[self.coating_roughness].enabled = self.coating
        self.inputs[self.coating_ior].enabled = self.coating
        self.inputs[self.coating_thickness].enabled = self.coating
        self.inputs[self.coating_transmission_color].enabled = self.coating
        self.coating_use_shader_normal_changed(context)

    def coating_use_shader_normal_changed(self, context):
        self.inputs[self.coating_normal].enabled = self.coating and not self.coating_use_shader_normal

    def emissive_changed(self, context):
        self.inputs[self.emissive_color].enabled = self.emissive
        self.inputs[self.emissive_weight].enabled = self.emissive

    def subsurface_changed(self, context):
        self.subsurface_use_diffuse_color_changed(context)
        self.inputs[self.subsurface_weight].enabled = self.subsurface
        self.inputs[self.subsurface_scatter_direction].enabled = self.subsurface
        self.inputs[self.subsurface_radius].enabled = self.subsurface

    def subsurface_use_diffuse_color_changed(self, context):
        self.inputs[self.subsurface_scatter_color].enabled = self.subsurface and not self.subsurface_use_diffuse_color        

    def normal_changed(self, context):
        self.inputs[self.normal_in].enabled = self.normal

    def transparency_changed(self, context):
        self.inputs[self.transparency_value].enabled = self.transparency

    def displacement_changed(self, context):
        self.inputs[self.displacement_map].enabled = self.displacement


    diffuse = bpy.props.BoolProperty(name='Diffuse', update=diffuse_changed, default=True)
    diffuse_use_shader_normal = bpy.props.BoolProperty(name='Use Shader Normal', update=diffuse_use_shader_normal_changed, default=True)
    backscatter_separate_color = bpy.props.BoolProperty(name='Separate Backscatter Color', update=backscatter_separate_color_changed, default=False)
    
    reflection = bpy.props.BoolProperty(name='Reflection', update=reflection_changed)
    reflection_mode = bpy.props.EnumProperty(name='Refletion Mode', 
                                             items=(('IOR', 'IOR', ''),
                                                    ('METALNESS', 'Metalness', '')), 
                                             default='IOR',
                                             update=reflection_mode_changed)
    reflection_use_shader_normal = bpy.props.BoolProperty(name='Use Shader Normal', update=reflection_use_shader_normal_changed, default=True)

    refraction = bpy.props.BoolProperty(name='Refraction', update=refraction_changed)
    refraction_thin_surface = bpy.props.BoolProperty(name='Refraction Thin Surface', default=False)
    refraction_caustics = bpy.props.BoolProperty(name='Allow Caustics', default=False)

    coating = bpy.props.BoolProperty(name='Coating', update=coating_changed)
    coating_use_shader_normal = bpy.props.BoolProperty(name='Use Shader Normal', update=coating_use_shader_normal_changed, default=True)

    sheen = bpy.props.BoolProperty(name='Sheen', update=sheen_changed, default=False)

    emissive = bpy.props.BoolProperty(name='Emissive', update=emissive_changed)
    emissive_double_sided = bpy.props.BoolProperty(name='Emissive Double Sided')
    emissive_intensity = bpy.props.FloatProperty(name='Emissive Intensity', min=0.0, default=1.0)

    subsurface = bpy.props.BoolProperty(name='Subsurface', update=subsurface_changed)
    subsurface_use_diffuse_color = bpy.props.BoolProperty(name='Subsurface Use Diffuse Color', update=subsurface_use_diffuse_color_changed)
    subsurface_multiple_scattering = bpy.props.BoolProperty(name='Subsurface Multiple Scattering', default=False)

    normal = bpy.props.BoolProperty(name='Normal', update=normal_changed, default=False)
    transparency = bpy.props.BoolProperty(name='Transparency', update=transparency_changed)

    displacement = bpy.props.BoolProperty(name='Displacement', update=displacement_changed)
    displacement_min_max_show = bpy.props.BoolProperty(name='Show/Hide', default=False)
    displacement_min = bpy.props.FloatProperty(name='Displacement Min', min=0.0, soft_max=10.0, default=0.0)
    displacement_max = bpy.props.FloatProperty(name='Displacement Max', min=0.0, soft_max=10.0, default=1.0)
    subdivision_show = bpy.props.BoolProperty(name='Show/Hide', default=False)

    def init(self, context):
        super(RPRShaderNode_Uber3, self).init()

        self.inputs.new('rpr_socket_color', self.diffuse_color).default_value = (0.5, 0.5, 0.5, 1.0)
        self.inputs.new('rpr_socket_weight_soft', self.diffuse_weight).default_value = 1.0
        self.inputs.new('rpr_socket_weight', self.diffuse_roughness).default_value = 0.5
        self.inputs.new('rpr_socket_link', self.diffuse_normal).hide_value = True
        self.inputs.new('rpr_socket_color', self.backscatter_color).default_value = (0.5, 0.5, 0.5, 1.0)
        self.inputs.new('rpr_socket_weight_soft', self.backscatter_weight).default_value = 0.0

        self.inputs.new('rpr_socket_color', self.reflection_color).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_weight_soft', self.reflection_weight).default_value = 1.0
        self.inputs.new('rpr_socket_weight', self.reflection_roughness).default_value = 0.25
        self.inputs.new('rpr_socket_float_MinN1_Max1', self.reflection_anisotropy).default_value = 0.0
        self.inputs.new('rpr_socket_angle360', self.reflection_anisotropy_rotation).default_value = 0.0
        self.inputs.new('rpr_socket_ior', self.reflection_ior)
        self.inputs.new('rpr_socket_weight', self.reflection_metalness).default_value = 0.0
        self.inputs.new('rpr_socket_link', self.reflection_normal).hide_value=True

        self.inputs.new('rpr_socket_color', self.refraction_color).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_weight_soft', self.refraction_weight).default_value = 1.0
        self.inputs.new('rpr_socket_weight', self.refraction_roughness).default_value = 0.0
        self.inputs.new('rpr_socket_ior', self.refraction_ior).default_value = 1.5
        self.inputs.new('rpr_socket_float_Min0_softMax10', self.refraction_absorption_distance).default_value = 0.0
        self.inputs.new('rpr_socket_color', self.refraction_absorption_color).default_value = (1.0, 1.0, 1.0, 1.0)

        self.inputs.new('rpr_socket_color', self.coating_color).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_weight', self.coating_weight).default_value =1.0
        self.inputs.new('rpr_socket_weight', self.coating_roughness).default_value = 0.01
        self.inputs.new('rpr_socket_ior', self.coating_ior).default_value = 1.5
        self.inputs.new('rpr_socket_float_Min0_softMax10', self.coating_thickness).default_value = 0.0
        self.inputs.new('rpr_socket_color', self.coating_transmission_color).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_link', self.coating_normal).hide_value=True

        self.inputs.new('rpr_socket_color', self.sheen_color).default_value = (0.5, 0.5, 0.5, 1.0)
        self.inputs.new('rpr_socket_weight_soft', self.sheen_weight).default_value = 1.0
        self.inputs.new('rpr_socket_weight', self.sheen_tint).default_value = 0.5

        self.inputs.new('rpr_socket_color', self.emissive_color).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_weight', self.emissive_weight).default_value = 1.0

        self.inputs.new('rpr_socket_weight', self.subsurface_weight).default_value = 1.0
        self.inputs.new('rpr_socket_color', self.subsurface_scatter_color).default_value = (0.436, 0.227, 0.131, 1.0)
        self.inputs.new('rpr_socket_scattering_radius', self.subsurface_radius)
        self.inputs.new('rpr_socket_scattering_direction', self.subsurface_scatter_direction).default_value = 0.0

        self.inputs.new('rpr_socket_link', self.normal_in).hide_value=True
        self.inputs.new('rpr_socket_weight', self.transparency_value).default_value = 1.0
        self.inputs.new('rpr_socket_link', self.displacement_map).hide_value=True

        self.diffuse_changed(context)
        self.reflection_changed(context)
        self.refraction_changed(context)
        self.coating_changed(context)
        self.sheen_changed(context)
        self.emissive_changed(context)
        self.subsurface_changed(context)
        self.normal_changed(context)
        self.transparency_changed(context)
        self.displacement_changed(context)

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.alignment = 'EXPAND'

        col.prop(self, 'diffuse', toggle=True)
        if self.diffuse:
            col.prop(self, 'diffuse_use_shader_normal', toggle=False)
            col.prop(self, 'backscatter_separate_color', toggle=False)

        col.prop(self, 'reflection', toggle=True)
        if self.reflection:
            col.separator()
            col.prop(self, 'reflection_mode')
            col.prop(self, 'reflection_use_shader_normal', toggle=False)

        col.prop(self, 'refraction', toggle=True)
        if self.refraction:
            col.prop(self, 'refraction_thin_surface', toggle=False)
            col.prop(self, 'refraction_caustics', toggle=False)

        col.prop(self, 'coating', toggle=True)
        if self.coating:
            col.prop(self, 'coating_use_shader_normal', toggle=False)

        col.prop(self, 'sheen', toggle=True)
        
        col.prop(self, 'emissive', toggle=True)
        if self.emissive:
            col.prop(self, 'emissive_double_sided', toggle=False)
            col.prop(self, 'emissive_intensity')
            col.separator()

        col.prop(self, 'subsurface', toggle=True)
        if self.subsurface:
            col.prop(self, 'subsurface_use_diffuse_color', toggle=False)
            col.prop(self, 'subsurface_multiple_scattering', toggle=False)

        col.prop(self, 'normal', toggle=True)
        col.prop(self, 'transparency', toggle=True)

        col.prop(self, 'displacement', toggle=True)
        if self.displacement:
            col1 = col.column(align=True)
            row = col1.row()
            row.label("Displacement Min/Max")
            row.prop(self, 'displacement_min_max_show', text='', icon='TRIA_UP' if self.displacement_min_max_show else 'TRIA_DOWN')
            if self.displacement_min_max_show:
                row1 = col1.row(align=True)
                row1.prop(self, 'displacement_min', slider=True, text='Min')
                row1.prop(self, 'displacement_max', slider=True, text='Max')
                col1.separator()
            
            row = col1.row()
            row.label("Subdivision Object Properties")
            row.prop(self, 'subdivision_show', text='', icon='TRIA_UP' if self.subdivision_show else 'TRIA_DOWN')
            if self.subdivision_show:
                col2 = col1.column()
                add_subdivision_properties(col2, bpy.context.active_object)

    def total_update(self):
        self.diffuse_changed(None)
        self.reflection_changed(None)
        self.refraction_changed(None)
        self.coating_changed(None)
        self.emissive_changed(None)
        self.subsurface_changed(None)
        self.subsurface_use_diffuse_color_changed(None)
        self.normal_changed(None)
        self.transparency_changed(None)
        self.diffuse_changed(None)


########################################################################################################################
# PBR node
########################################################################################################################
@rpraddon.register_class
class RPRShaderNode_PBR(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_pbr'
    bl_label = 'RPR PBR'
    bl_width_min = 300

    base_color = 'Base Color'
    roughness = 'Roughness'
    metalness = 'Metalness'
    specular = 'Specular'

    normal_in = 'Normal'

    emissive_color = 'Emissive Color'
    emissive_weight = 'Emissive Weight'
    emissive_intensity = 'Emissive Intensity'

    glass_weight = 'Glass'
    glass_ior = 'Glass IOR'

    sss_weight = 'Subsurface Weight'
    sss_color = 'Subsurface Color'
    sss_radius = 'Subsurface Radius' 
    
    def init(self, context):
        super(RPRShaderNode_PBR, self).init()

        self.inputs.new('rpr_socket_color', self.base_color).default_value = (0.5, 0.5, 0.5, 1.0)
        self.inputs.new('rpr_socket_weight', self.roughness).default_value = 0.25
        self.inputs.new('rpr_socket_weight', self.metalness).default_value = 0.0
        self.inputs.new('rpr_socket_weight', self.specular).default_value = 1.0

        self.inputs.new('rpr_socket_weight_soft', self.emissive_weight).default_value = 0.0
        self.inputs.new('rpr_socket_color', self.emissive_color).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_factor', self.emissive_intensity).default_value = 1.0
        
        self.inputs.new('rpr_socket_weight_soft', self.glass_weight).default_value = 0.0
        self.inputs.new('rpr_socket_ior', self.glass_ior).default_value = 1.5
        
        self.inputs.new('rpr_socket_weight_soft', self.sss_weight).default_value = 0.0
        self.inputs.new('rpr_socket_color', self.sss_color).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_color', self.sss_radius).default_value = (3.67, 1.37, 0.68, 1.0)  # skin values

        self.inputs.new('rpr_socket_link', self.normal_in)
        
    def draw_buttons(self, context, layout):
        pass
             

########################################################################################################################
# PBR3 node
########################################################################################################################
@rpraddon.register_class
class RPRShaderNode_PBR3(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_pbr3'
    bl_label = 'RPR PBR'
    bl_width_min = 300

    base_color = 'Base Color'
    roughness = 'Roughness'
    metalness = 'Metalness'
    specular = 'Specular'
    normal = 'Normal'

    emissive_color = 'Emissive Color'
    emissive_weight = 'Emissive Weight'

    glass_weight = 'Glass'
    glass_ior = 'Glass IOR'

    subsurface_weight = 'Subsurface Weight'
    subsurface_color = 'Subsurface Color'
    subsurface_radius = 'Subsurface Radius' 
    
    def init(self, context):
        super(RPRShaderNode_PBR3, self).init()

        self.inputs.new('rpr_socket_color', self.base_color).default_value = (0.5, 0.5, 0.5, 1.0)
        self.inputs.new('rpr_socket_weight', self.roughness).default_value = 0.25
        self.inputs.new('rpr_socket_weight', self.metalness).default_value = 0.0
        self.inputs.new('rpr_socket_weight', self.specular).default_value = 1.0
        self.inputs.new('rpr_socket_link', self.normal).hide_value=True

        self.inputs.new('rpr_socket_weight', self.glass_weight).default_value = 0.0
        self.inputs.new('rpr_socket_ior', self.glass_ior).default_value = 1.5

        self.inputs.new('rpr_socket_weight', self.emissive_weight).default_value = 0.0
        self.inputs.new('rpr_socket_color', self.emissive_color).default_value = (1.0, 1.0, 1.0, 1.0)
        
        self.inputs.new('rpr_socket_weight', self.subsurface_weight).default_value = 0.0
        self.inputs.new('rpr_socket_color', self.subsurface_color).default_value = (0.436, 0.227, 0.131, 1.0)
        self.inputs.new('rpr_socket_scattering_radius', self.subsurface_radius)
        
    def draw_buttons(self, context, layout):
        pass

########################################################################################################################
# Arithmetics nodes
########################################################################################################################
class RPRNodeType_Arithmetics(RPRTreeNode):
    value_out = 'Out'
    bl_icon = 'MATERIAL'

    def init(self):
        self.outputs.new('rpr_socket_value', self.value_out)

@rpraddon.register_class
class RPRValueNode_Blend(RPRNodeType_Arithmetics):
    bl_idname = 'rpr_arithmetics_node_value_blend'
    bl_label = 'RPR Value Blend'

    weight_in = 'Weight'
    value1_in = 'Value 1'
    value2_in = 'Value 2'

    def change_type(self, context):
        socket1 = self.inputs[self.value1_in]
        socket2 = self.inputs[self.value2_in]
        socket1.type = self.type
        socket2.type = self.type

    type = bpy.props.EnumProperty(name='Type',
                                  items=RPRSocketValue.get_value_types(),
                                  default='color', update=change_type)

    def init(self, context):
        super(RPRValueNode_Blend, self).init()
        self.inputs.new('rpr_socket_weight', self.weight_in)
        self.inputs.new('rpr_socket_value', self.value1_in)
        self.inputs.new('rpr_socket_value', self.value2_in)
        self.change_type(context)

    def draw_buttons(self, context, layout):
        layout.prop(self, 'type', expand=True)


@rpraddon.register_class
class RPRValueNode_Math(RPRNodeType_Arithmetics):
    bl_idname = 'rpr_arithmetics_node_math'
    bl_label = 'RPR Math'

    value1_in = 'Value 1'
    value2_in = 'Value 2'
    value3_in = 'Value 3'

    def change_params_type(self, context):
        self.inputs[0].type = self.type
        self.inputs[1].type = self.type
        self.inputs[2].type = self.type

    def change_op(self, context):
        el = self.op_settings[self.op]
        params = el['params']
        for i in range(0, 3):
            if i in params:
                self.inputs[i].name = params[i][0]
                self.inputs[i].enabled = True
            else:
                self.inputs[i].enabled = False

    op_settings = OrderedDict([
        ('ABS', {
            'name': 'Abs',
            'params': {
                0: ['Value'],
            },
        }),
        ('ACOS', {
            'name': 'Arccosine',
            'params': {
                0: ['Value'],
            },
        }),
        ('ADD', {
            'name': 'Add',
            'params': {
                0: ['Value 1'],
                1: ['Value 2'],
            },
        }),
        ('ASIN', {
            'name': 'Arcsine',
            'params': {
                0: ['Value'],
            },
        }),
        ('ATAN', {
            'name': 'Arctangent',
            'params': {
                0: ['Value'],
            },
        }),
        ('AVERAGE', {
            'name': 'Average',
            'params': {
                0: ['Value 1'],
                1: ['Value 2'],
            },
        }),
        ('AVERAGE_XYZ', {
            'name': 'Average XYZ',
            'params': {
                0: ['Value'],
            },
        }),
        ('COMBINE', {
            'name': 'Combine',
            'params': {
                0: ['Value 1'],
                1: ['Value 2'],
                2: ['Value 3'],
            },
        }),
        ('COS', {
            'name': 'Cosine',
            'params': {
                0: ['Value'],
            },
        }),
        ('CROSS3', {
            'name': 'Cross Product',
            'params': {
                0: ['Value 1'],
                1: ['Value 2'],
            },
        }),
        ('DOT3', {
            'name': 'Dot3 Product',
            'params': {
                0: ['Value 1'],
                1: ['Value 2'],
            },
        }),
        ('FLOOR', {
            'name': 'Floor',
            'params': {
                0: ['Value'],
            },
        }),
        ('LENGTH3', {
            'name': 'Length3',
            'params': {
                0: ['Value'],
            },
        }),
        ('MAX', {
            'name': 'Max',
            'params': {
                0: ['Value 1'],
                1: ['Value 2'],
            },
        }),
        ('MIN', {
            'name': 'Min',
            'params': {
                0: ['Value 1'],
                1: ['Value 2'],
            },
        }),
        ('MOD', {
            'name': 'Mod',
            'params': {
                0: ['Value 1'],
                1: ['Value 2'],
            },
        }),
        ('MUL', {
            'name': 'Multiply',
            'params': {
                0: ['Value 1'],
                1: ['Value 2'],
            },
        }),
        ('NORMALIZE3', {
            'name': 'Normalize',
            'params': {
                0: ['Value'],
            },
        }),
        ('POW', {
            'name': 'Pow',
            'params': {
                0: ['Value 1'],
                1: ['Value 2'],
            },
        }),
        ('SELECT_X', {
            'name': 'Select X',
            'params': {
                0: ['Value'],
            },
        }),
        ('SELECT_Y', {
            'name': 'Select Y',
            'params': {
                0: ['Value'],
            },
        }),
        ('SELECT_Z', {
            'name': 'Select Z',
            'params': {
                0: ['Value'],
            },
        }),
        ('SIN', {
            'name': 'Sine',
            'params': {
                0: ['Value'],
            },
        }),
        ('SUB', {
            'name': 'Subtract',
            'params': {
                0: ['Value 1'],
                1: ['Value 2'],
            },
        }),
        ('TAN', {
            'name': 'Tangent',
            'params': {
                0: ['Value'],
            },
        }),
        ('DIV', {
            'name': 'Divide',
            'params': {
                0: ['Value 1'],
                1: ['Value 2'],
            },
        }),
        ('DOT4', {
            'name': 'Dot4 Product',
            'params': {
                0: ['Value 1'],
                1: ['Value 2'],
            },
        }),
        ('SELECT_W', {
            'name': 'Select W',
            'params': {
                0: ['Value'],
            },
        }),
        ])

    def get_op_items(settings):
        items = []
        indices = list(settings)
        for k in sorted(settings, key=lambda k: settings[k]['name']):
            name = settings[k]['name']
            items.append((k, name, name, indices.index(k)))
        return items

    type = bpy.props.EnumProperty(name='Type',
                                  items=RPRSocketValue.get_value_types(),
                                  default='color', update=change_params_type)

    op = bpy.props.EnumProperty(name='Operation',
                                items=get_op_items(op_settings),
                                default='ADD', update=change_op)

    use_clamp = bpy.props.BoolProperty(name='Clamp',
                                description="Clamp result of the node to 0..1 range",
                                default=False)

    def init(self, context):
        super(RPRValueNode_Math, self).init()
        self.inputs.new('rpr_socket_value', self.value1_in)
        self.inputs.new('rpr_socket_value', self.value2_in)
        self.inputs.new('rpr_socket_value', self.value3_in)
        self.change_params_type(context)
        self.change_op(context)

    def draw_buttons(self, context, layout):
        layout.prop(self, 'op', text='')
        layout.prop(self, 'use_clamp')
        layout.prop(self, 'type', expand=True)

    def draw_label(self):
        el = self.op_settings[self.op]
        return self.bl_label + ' - ' + el['name']


########################################################################################################################
# Inputs nodes
########################################################################################################################
class RPRNodeType_Input(RPRTreeNode):
    value_out = 'Out'
    bl_icon = 'TEXTURE'

    def init(self):
        self.outputs.new('rpr_socket_color', self.value_out)

@rpraddon.register_class
class RPRMaterialNode_Constant(RPRNodeType_Input):
    bl_idname = 'rpr_input_node_constant'
    bl_label = 'RPR Color'

    color = bpy.props.FloatVectorProperty(name='Color', subtype='COLOR', min=0.0, max=1.0,
                                          size=4, default=(1.0, 1.0, 1.0, 1.0))
    def init(self, context):
        super(RPRMaterialNode_Constant, self).init()

    def draw_buttons(self, context, layout):
        layout.template_color_picker(self, 'color', value_slider=True)
        layout.prop(self, 'color', text='')


@rpraddon.register_class
class RPRMaterialNode_Value(RPRNodeType_Input):
    bl_idname = 'rpr_input_node_value'
    bl_label = 'RPR Value'

    def init(self, context):
        super(RPRMaterialNode_Value, self).init()

    def get_value_types():
        return (('float', "Float", "Float"),
                ('vector', "Vector", "Vector"))

    def value_to_vector4(self):
        if self.type == 'float':
            return (self.value_float, self.value_float, self.value_float, self.value_float)
        else:
            return self.value_vector4

    @staticmethod
    def is_vector4_equal(a, b):
        return list(a) == list(b)

    def update_value(self, context):
        if self.type == 'float':
            self.value_float = self.default_value[0]
        else:
            self.value_vector4 = self.default_value

    def update_default_value(self, context):
        val = self.value_to_vector4()
        self['default_value'] = val

        if self.type != 'vector':
            self['value_vector4'] = self.default_value
        if self.type == 'float':
            self['value_float'] = self.default_value[0]

    type = bpy.props.EnumProperty(
        name='Type',
        items=get_value_types(),
        default='float'
    )

    show = bpy.props.BoolProperty(name="Show/Hide", default=False)

    value_vector4 = bpy.props.FloatVectorProperty(name="Vector4", size=4,
                                                default = (0, 0, 0, 0),
                                                update=update_default_value)
    value_float = bpy.props.FloatProperty(name="Value", default=0, update=update_default_value)
    default_value = bpy.props.FloatVectorProperty(name="Vector4", size=4,
                                                default=(0, 0, 0, 0),
                                                update=update_value)

    def draw_buttons(self, context, layout):
        layout.prop(self, 'type', expand=True)
        if self.type == 'float':
            layout.prop(self, 'value_float')
        else:
            col = layout.column()
            row = col.row()
            row.label(text='Value')
            row.prop(self, 'show', text='', icon='TRIA_UP' if self.show else 'TRIA_DOWN')
            if self.show:
                col.prop(self, 'value_vector4', text='')


@rpraddon.register_class
class RPRMaterialNode_NormalMap(RPRNodeType_Input):
    bl_idname = 'rpr_input_node_normalmap'
    bl_label = 'RPR NormalMap'

    map_in = 'Map'
    scale_in = 'Scale'

    flip_x = bpy.props.BoolProperty(name='Flip X',
                                description="Flip X coordinate",
                                default=False)

    flip_y = bpy.props.BoolProperty(name='Flip Y',
                                description="Flip Y coordinate",
                                default=False)

    def init(self, context):
        super(RPRMaterialNode_NormalMap, self).init()
        self.inputs.new('rpr_socket_color', self.map_in)
        input_scale = self.inputs.new('rpr_socket_float', self.scale_in)
        input_scale.default_value = 1.0

    def draw_buttons(self, context, layout):
        row = layout.row()
        row.prop(self, 'flip_x')
        row.prop(self, 'flip_y')


@rpraddon.register_class
class RPRMaterialNode_BumpMap(RPRNodeType_Input):
    bl_idname = 'rpr_input_node_bumpmap'
    bl_label = 'RPR BumpMap'

    map_in = 'Map'
    scale_in = 'Scale'

    def init(self, context):
        super(RPRMaterialNode_BumpMap, self).init()
        self.inputs.new('rpr_socket_color', self.map_in)
        input_scale = self.inputs.new('rpr_socket_float', self.scale_in)
        input_scale.default_value = 1.0


@rpraddon.register_class
class RPRMaterialNode_Lookup(RPRNodeType_Input):
    bl_idname = 'rpr_input_node_lookup'
    bl_label = 'RPR Lookup'

    items = (('UV', "UV", "texture coordinates"),
             ('N', "Normal", "normal"),
             ('P', "Position", "world position"),
             ('INVEC', "InVec", "Incident direction"),
             ('OUTVEC', "OutVec", "Outgoing direction"))

    type = bpy.props.EnumProperty(name='Type',
                                  items=items,
                                  default='UV')

    def init(self, context):
        super(RPRMaterialNode_Lookup, self).init()

    def draw_buttons(self, context, layout):
        layout.prop(self, 'type')

    def draw_label(self):
        name = [val[1] for val in self.items if self.type == val[0]][0]
        return self.bl_label + ' - ' + name


########################################################################################################################
# Mapping nodes
########################################################################################################################
class RPRNodeType_Mapping(RPRTreeNode):
    value_out = 'Out'
    bl_icon = 'TEXTURE'

    def init(self):
        self.outputs.new('rpr_socket_transform', self.value_out)


@rpraddon.register_class
class RPRMaterialNode_Mapping(RPRNodeType_Mapping):
    bl_idname = 'rpr_mapping_node'
    bl_label = 'RPR Texture Mapping'
    bl_width_min = 195

    scale_in = 'Scale UV'
    offset_in = 'Offset UV'

    def init(self, context):
        super(RPRMaterialNode_Mapping, self).init()
        scale_uv = self.inputs.new('rpr_socket_uv', self.scale_in)
        self.inputs.new('rpr_socket_uv', self.offset_in)
        scale_uv.default_value = (1.0, 1.0)


@rpraddon.register_class
class RPRMaterialNode_ProceduralMapping(RPRNodeType_Mapping):
    bl_idname = 'rpr_procedural_mapping_node'
    bl_label = 'RPR Procedural Texture Mapping'
    bl_width_min = 195

    items = (('MATERIAL_NODE_UVTYPE_PLANAR', 'Plane', 'Planar projection'),
             ('MATERIAL_NODE_UVTYPE_CYLINDICAL', 'Cylinder', 'Cylidrical projection'),
             ('MATERIAL_NODE_UVTYPE_SPHERICAL', 'Sphere', 'Spherical projection'),
            )

    shape_type = bpy.props.EnumProperty(name='Shape',
                                  items=items,
                                  default='MATERIAL_NODE_UVTYPE_SPHERICAL')

    rotation = bpy.props.FloatVectorProperty(
        name="Rotation",
        default=(0.0, 0.0, 0.0),
        size=3, subtype='EULER'
    )

    scale = bpy.props.FloatVectorProperty(
        name="Scale",
        default=(1.0, 1.0, 1.0),
        size=3, subtype='XYZ'
    )

    location = bpy.props.FloatVectorProperty(
        name="Location",
        default=(0.0, 0.0, 0.0),
        size=3, subtype='XYZ'
    )

    def init(self, context):
        super(RPRMaterialNode_ProceduralMapping, self).init()
    
    def draw_buttons(self, context, layout):
        layout.prop(self, 'shape_type')
        layout.prop(self, 'location')
        layout.prop(self, 'rotation')
        layout.prop(self, 'scale')

@rpraddon.register_class
class RPRMaterialNode_TriplanarMapping(RPRNodeType_Mapping):
    bl_idname = 'rpr_triplanar_mapping_node'
    bl_label = 'RPR Triplanar Texture Mapping'
    bl_width_min = 195

    rotation = bpy.props.FloatVectorProperty(
        name="Rotation",
        default=(0.0, 0.0, 0.0),
        size=3, subtype='EULER'
    )

    location = bpy.props.FloatVectorProperty(
        name="Location",
        default=(0.0, 0.0, 0.0),
        size=3, subtype='XYZ'
    )

    weight = bpy.props.FloatProperty(
        name="Blend Weight",
        default=0.0,
        description='Amount to blend edges',
    )

    def init(self, context):
        super(RPRMaterialNode_TriplanarMapping, self).init()
    
    def draw_buttons(self, context, layout):
        layout.prop(self, 'location')
        layout.prop(self, 'rotation')
        layout.prop(self, 'weight')


@rpraddon.register_class
class RPRMaterialNode_ProjectionMapping(RPRNodeType_Mapping):
    bl_idname = 'rpr_projection_mapping_node'
    bl_label = 'RPR Projection Texture Mapping'
    bl_width_min = 195

    camera = bpy.props.StringProperty(name='camera',
                                  description="Camera to project from",
                                  default='')

    threshold = bpy.props.FloatProperty(
        name="Threshold",
        default=999999,
        description='Distance from camera to cutoff projection'
    )

    def init(self, context):
        super(RPRMaterialNode_ProjectionMapping, self).init()
    
    def draw_buttons(self, context, layout):
        layout.prop_search(self, 'camera', bpy.data, 'cameras')
        layout.prop(self, 'threshold')

########################################################################################################################
# Texture nodes
########################################################################################################################
class RPRNodeType_Texture(RPRTreeNode):
    value_out = 'Out'
    bl_icon = 'TEXTURE'

    def init(self):
        self.outputs.new('rpr_socket_color', self.value_out)


preview_collections = {}


@rpraddon.register_class
class RPR_OT_open_image_wrapper(bpy.types.Operator):
    bl_idname = "rpr.open_image_wrapper"
    bl_label = "Open Image"
    bl_description = "Open Image"

    relative_path = bpy.props.BoolProperty(
        name="Relative Path",
        description="Select the file relative to the blend file",
        default=False,
    )

    filepath = bpy.props.StringProperty(subtype="FILE_PATH")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        image = load_image(bpy.path.abspath(self.filepath))
        image.filepath = self.filepath

        for node in context.space_data.node_tree.nodes:
            if node.bl_idname == 'rpr_texture_node_image_map' and node.requested_load:
                node.image_name = image.name
                node.requested_load = False
                break

        return {'FINISHED'}


@rpraddon.register_class
class RPRMaterialNode_ImageMap(RPRNodeType_Texture):
    bl_idname = 'rpr_texture_node_image_map'
    bl_label = 'RPR Image Map'
    bl_width_min = 200

    mapping_in = 'Mapping'

    # items for texture gamma

    items = (('Linear', "Linear", "Linear"),
             ('sRGB', "sRGB", "sRGB"))
    color_space_type = bpy.props.EnumProperty(name='Color Space',
                                  items=items,
                                  default='Linear')


    # items for texture wrap
    wrap_items = (('REPEAT', "Repeat", "Repeating Texture"),
             ('MIRRORED_REPEAT', "Mirror", "Texture mirrors outside of 0-1"),
             ('CLAMP_TO_EDGE', "Clamp to Edge", "Clamp to Edge.  Outside 0-1 the texture will smear."),
             ('CLAMP_ZERO', "Clamp to Black", "Clamp to Black outside 0-1"),
             ('CLAMP_ONE', "Clamp to White", "Clamp to White outside 0-1"),)

    wrap_type = bpy.props.EnumProperty(name='Wrap Type',
                                  items=wrap_items,
                                  default='REPEAT')

    def generate_preview(self, context):
        name = self.name + '_' + self.id_data.name
        if name not in preview_collections:
            item = bpy.utils.previews.new()
            item.previews = ()
            item.image_name = ''
            preview_collections[name] = item

        item = preview_collections[name]
        wm = context.window_manager

        enum_items = []

        img = self.get_image()
        if img:
            new_image_name =img.name
            if item.image_name == new_image_name:
                return item.previews
            else:
                item.image_name = new_image_name

            item.clear()

            thumb = item.load(img.name, bpy.path.abspath(img.filepath), 'IMAGE')
            enum_items = [(img.filepath, img.name, '', thumb.icon_id, 0)]

        item.previews = enum_items
        return item.previews

    if versions.is_blender_support_new_image_node():
        image = bpy.props.PointerProperty(type=bpy.types.Image)
    else:
        def load_image(self, context):
            self.requested_load = True
            bpy.ops.rpr.open_image_wrapper('INVOKE_DEFAULT')
            self['open_image_button'] = False

        def update_image(self, context):
            if self.image_name in bpy.data.images:
                image = bpy.data.images[self.image_name]
                image.use_fake_user = True
                self.texturePath = image.filepath

        texturePath = bpy.props.StringProperty(name='', description='Image Map Path')
        image_name = bpy.props.StringProperty(default='', update=update_image)
        requested_load = bpy.props.BoolProperty()
        open_image_button = bpy.props.BoolProperty(name='Open', description='Open a new image', update=load_image)

    preview = bpy.props.EnumProperty(items=generate_preview)

    def init(self, context):
        super(RPRMaterialNode_ImageMap, self).init()
        self.inputs.new('rpr_socket_transform', self.mapping_in)

    def draw_buttons(self, context, layout):
        if versions.is_blender_support_new_image_node():
            layout.template_ID(self, "image", open="image.open")
            layout.template_icon_view(self, 'preview', show_labels=True)
        else:
            split = layout.split(align=True, percentage=0.7)
            split.prop_search(self, 'image_name', bpy.data, 'images', text='')
            split.prop(self, 'open_image_button', toggle=True, icon='FILESEL')
            layout.template_icon_view(self, 'preview', show_labels=True)

        layout.prop(self, 'color_space_type')
        layout.prop(self, 'wrap_type')

    def draw_label(self):
        img = self.get_image()
        if not img:
            return self.name
        return img.name

    def get_image(self):
        if versions.is_blender_support_new_image_node():
            return self.image
        else:
            return bpy.data.images[self.image_name] if self.image_name in bpy.data.images else None


@rpraddon.register_class
class RPRMaterialNode_Noise2D(RPRNodeType_Texture):
    bl_idname = 'rpr_texture_node_noise2d'
    bl_label = 'RPR Noise 2D'

    mapping_in = 'Mapping'

    has_thumbnail = True
    thumbnail = bpy.props.EnumProperty(items=RPRTreeNode.get_thumbnail_enum)

    def init(self, context):
        super(RPRMaterialNode_Noise2D, self).init()
        self.inputs.new('rpr_socket_transform', self.mapping_in)

    def draw_buttons(self, context, layout):
        self.draw_thumbnail(layout)


@rpraddon.register_class
class RPRMaterialNode_Gradient(RPRNodeType_Texture):
    bl_idname = 'rpr_texture_node_gradient'
    bl_label = 'RPR Gradient'

    color1_in = "Color 1"
    color2_in = "Color 2"
    mapping_in = 'Mapping'

    has_thumbnail = True
    thumbnail = bpy.props.EnumProperty(items=RPRTreeNode.get_thumbnail_enum)

    def init(self, context):
        super(RPRMaterialNode_Gradient, self).init()
        input_color1 = self.inputs.new('rpr_socket_color', self.color1_in)
        input_color1.default_value = (0, 0, 0, 1)
        input_color2 = self.inputs.new('rpr_socket_color', self.color2_in)
        input_color2.default_value = (1, 1, 1, 1)
        self.inputs.new('rpr_socket_transform', self.mapping_in)

    def draw_buttons(self, context, layout):
        self.draw_thumbnail(layout)


@rpraddon.register_class
class RPRMaterialNode_Checker(RPRNodeType_Texture):
    bl_idname = 'rpr_texture_node_checker'
    bl_label = 'RPR Checker'

    mapping_in = 'Mapping'

    has_thumbnail = True
    thumbnail = bpy.props.EnumProperty(items=RPRTreeNode.get_thumbnail_enum)

    def init(self, context):
        super(RPRMaterialNode_Checker, self).init()
        self.inputs.new('rpr_socket_transform', self.mapping_in)

    def draw_buttons(self, context, layout):
        self.draw_thumbnail(layout)


@rpraddon.register_class
class RPRMaterialNode_AO(RPRNodeType_Texture):
    bl_idname = 'rpr_texture_node_ao'
    bl_label = 'RPR Ambient Occlusion'

    radius = bpy.props.FloatProperty(name='radius', min=-0.0, soft_max=10.0, default=0.1)
    side = bpy.props.EnumProperty(name = 'side',
                                  items={('FRONT', 'Front', 'Front'),
                                         ('BACK', 'Back', 'Back')},
                                  default='FRONT')
    thumbnail = bpy.props.EnumProperty(items=RPRTreeNode.get_thumbnail_enum)
    occluded_color = "Occluded Color"
    unoccluded_color = "Unoccluded Color"

    def init(self, context):
        super(RPRMaterialNode_AO, self).init()
        self.inputs.new('rpr_socket_color', self.unoccluded_color)
        self.inputs.new('rpr_socket_color', self.occluded_color).default_value = (0.0, 0.0, 0.0, 1.0) 
   
    def draw_buttons(self, context, layout):
        self.draw_thumbnail(layout)
        layout.prop(self, 'radius')
        layout.prop(self, 'side')


@rpraddon.register_class
class RPRMaterialNode_Dot(RPRNodeType_Texture):
    bl_idname = 'rpr_texture_node_dot'
    bl_label = 'RPR Dot'

    mapping_in = 'Mapping'

    def init(self, context):
        super(RPRMaterialNode_Dot, self).init()
        self.inputs.new('rpr_socket_transform', self.mapping_in)


########################################################################################################################
# Fresnel nodes
########################################################################################################################
class RPRNodeType_Fresnel(RPRTreeNode):
    value_out = 'Out'
    bl_icon = 'TEXTURE'

    def init(self):
        self.outputs.new('rpr_socket_color', self.value_out)


@rpraddon.register_class
class RPRMaterialNode_FresnelSchlick(RPRNodeType_Fresnel):
    bl_idname = 'rpr_fresnel_schlick_node'
    bl_label = 'RPR Fresnel Schlick'

    reflectance_in = 'Reflectance'
    normal_in = 'Normal'
    in_vec_in = 'InVec'

    def init(self, context):
        super(RPRMaterialNode_FresnelSchlick, self).init()
        self.inputs.new('rpr_socket_weight', self.reflectance_in)
        self.inputs.new('rpr_socket_link', self.normal_in)
        self.inputs.new('rpr_socket_link', self.in_vec_in)


@rpraddon.register_class
class RPRMaterialNode_Fresnel(RPRNodeType_Fresnel):
    bl_idname = 'rpr_fresnel_node'
    bl_label = 'RPR Fresnel'

    ior_in = 'IOR'
    normal_in = 'Normal'
    in_vec_in = 'InVec'

    def init(self, context):
        super(RPRMaterialNode_Fresnel, self).init()
        self.inputs.new('rpr_socket_ior', self.ior_in)
        self.inputs.new('rpr_socket_link', self.normal_in).hide_value=True
        self.inputs.new('rpr_socket_link', self.in_vec_in).hide_value=True


@rpraddon.register_class
class RPRMaterialNode_FresnelColorBlend(RPRNodeType_Fresnel):
    bl_idname = 'rpr_fresnel_color_blend_node'
    bl_label = 'RPR Fresnel Color Blend'

    color1 = 'Color 1'
    color2 = 'Color 2'
    pos1 = bpy.props.FloatProperty(name='Pos 1', soft_min=0.0, soft_max=1.0, default=0.01)
    pos2 = bpy.props.FloatProperty(name='Pos 2', soft_min=0.0, soft_max=1.0, default=0.99)

    def init(self, context):
        super(RPRMaterialNode_FresnelColorBlend, self).init()
        self.inputs.new('rpr_socket_color', self.color1).default_value = (1.0, 1.0, 1.0, 1.0)
        self.inputs.new('rpr_socket_color', self.color2).default_value = (0.0, 0.0, 0.0, 1.0)

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, 'pos1', slider=True)
        col.prop(self, 'pos2', slider=True)


########################################################################################################################
# Other nodes
########################################################################################################################

@rpraddon.register_class
class RPRShaderNode_Displacement(RPRNodeType_Shader):
    bl_idname = 'rpr_shader_node_displacement'
    bl_label = 'RPR Displacement'
    bl_width_min = 200

    map_in = 'Displacement Map'
    scale_min = bpy.props.FloatProperty(name='Scale Min', min=-1.0, max=1.0, default=0.0)
    scale_max = bpy.props.FloatProperty(name='Scale Max', min=-1.0, max=1.0, default=1.0)

    shader_out = 'Displacement'

    def init(self, context):
        super().init()
        self.inputs.new('rpr_socket_color', self.map_in)

    def draw_buttons(self, context, layout):
        add_subdivision_properties(layout, bpy.context.active_object)
        layout.prop(self, 'scale_min', slider=True)
        layout.prop(self, 'scale_max', slider=True)


########################################################################################################################
# Groups support nodes
########################################################################################################################
GROUP_IO_NODE_COLOR = (0.7, 0.72, 0.6)

@rpraddon.register_class
class RPRDummySocket(bpy.types.NodeSocket):
    bl_idname = "rpr_dummy_socket"
    bl_label = "RPR Dummy Socket"

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.6, 0.6, 0.6, 0.5)

@rpraddon.register_class
class RPRShaderGroupInputsNode(RPRNodeSocketConnectorHelper, RPRTreeNode):
    bl_idname = 'rpr_shader_node_group_input'
    bl_label = 'Group Inputs'
    bl_icon = 'MATERIAL'
    bl_width_min = 100

    def init(self, context):
        self.use_custom_color = True
        self.color = GROUP_IO_NODE_COLOR
        self.outputs.new('rpr_dummy_socket', '')
        self.node_kind = 'outputs'


@rpraddon.register_class
class RPRShaderGroupOutputsNode(RPRNodeSocketConnectorHelper, RPRTreeNode):
    bl_idname = 'rpr_shader_node_group_output'
    bl_label = 'Group Outputs'
    bl_icon = 'MATERIAL'
    bl_width_min = 100

    def init(self, context):
        self.use_custom_color = True
        self.color = GROUP_IO_NODE_COLOR
        self.inputs.new('rpr_dummy_socket', '')
        self.node_kind = 'inputs'