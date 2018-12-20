import sys

import bpy
import pyrpr
import pyrprx
from bpy.types import Operator
from bpy_extras.node_utils import find_node_input

from rprblender.ui import RPR_Panel
from rprblender.utils import logging
from . import RPR_Properties


log = logging.Log(tag='Material')


class RPR_MATERIAL_OT_UseShadingNodes(Operator):
    """
    Enable nodes on a material, world or light
    """
    bl_idname = 'rpr.use_material_shading_nodes'
    bl_label = "Use Nodes"

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return hasattr(context, 'material')

    def execute(self, context: bpy.types.Context):
        log("Enabling nodes for {}".format(context))
        if context.material:
            context.material.use_nodes = True

        return {'FINISHED'}


class RPR_MATERIAL_parser(RPR_Properties):
    def sync(self, rpr_context) -> pyrprx.Material:
        mat = self.id_data
        log("Syncing material: %s" % mat.name)
        key = mat.as_pointer()
        tree = getattr(mat, 'node_tree', None)

        if not tree:
            # "ERROR" shader
            return self.create_fake_material(rpr_context, (1.0, 0.0, 1.0, 1.0))

        # Look for output node
        node = find_rpr_output_node(tree)
        if not node:
            node = find_cycles_output_node(tree)
            if not node:
                log("No valid output node found!")
                return self.create_fake_material(rpr_context, (1.0, 0.0, 1.0, 1.0))
            else:
                log("Blender output node found: {}".format(node))
                try:
                    result = self.parse_cycles_output_node(rpr_context, node)
                except Exception as e:
                    tb = sys.exc_info()[2]
                    log("Cycles material parsing exception {}".format(e.with_traceback(tb)))
                    result = self.create_fake_material(rpr_context, (1.0, 0.0, 1.0, 1.0))
                return result
        if not hasattr(node, 'sync'):
            log("No valid output node found!")
            return self.create_fake_material(rpr_context, (1.0, 0.0, 1.0, 1.0))

        log("Output node {}".format(node))

        # Parse it
        material = node.sync(rpr_context)
        log("Material parsed as {}".format(material))

        # Fake material for tests
        if not material:
            color = (0.9, 0.4, 0.4, 1.0)
            material = self.create_fake_material(rpr_context, color)

        return material

    @staticmethod
    def get_socket(node, name=None, index=None):
        if name:
            try:
                socket = node.inputs[name]
            except KeyError:
                return None
        elif index:
            try:
                socket = node.inputs[index]
            except IndexError:
                return None
        else:
            return None

        log("get_socket({}, {}, {}): {}; linked {}; links number {}".
                     format(node, name, index, socket, socket.is_linked, len(socket.links)))
        if socket.is_linked and len(socket.links) > 0:
            return socket.links[0].from_socket
        return None

    def create_fake_material(self, rpr_context, color: tuple) -> pyrprx.Material:
        null_vector = (0, 0, 0, 0)
        key = self.id_data.name
        if not key:
            key = "Unnamed_{}".format(self)
        rpr_mat = rpr_context.create_material(key, pyrprx.MATERIAL_UBER)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_DIFFUSE_COLOR, color)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, (1.0, 1.0, 1.0, 1.0))
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS, (0.5, 0.5, 0.5, 0.5))
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_WEIGHT, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_EMISSION_WEIGHT, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SSS_WEIGHT, null_vector)
        return rpr_mat

    def parse_cycles_output_node(self, rpr_context, node):
        material = None
        input = self.get_socket(node, name='Surface')  # 'Surface'
        log("Material Output input['Surface'] linked to {}".format(input))
        input_node = input.node
        log("syncing {}".format(input_node))
        # TODO replace with conversion "Cycles -> RPR" table
        if input_node.bl_idname == 'ShaderNodeBsdfPrincipled':
            material = self.parse_cycles_principled(rpr_context, input_node)
        elif input_node.bl_idname == 'ShaderNodeBsdfPrincipled':
            material = input_node.sync(rpr_context)
        return material

    def parse_cycles_principled(self, rpr_context, node) -> pyrprx.Material:
        def get_value(name):
            socket = node.inputs[name]
            log("input {} value is {}".format(name, socket.default_value))
            if socket:
                val = socket.default_value
                if isinstance(val, float) or isinstance(val, int):
                    return (val, val, val, val)
                elif len(val) == 3:
                    return (val[0], val[1], val[2], 1.0)
                elif len(val) == 4:
                    return val[0:4]
                raise Exception("Unknown socket '{}' value type '{}'".format(socket, type(socket)))

        base_color = get_value('Base Color')
        roughness = get_value('Roughness')
        subsurface = get_value('Subsurface')
        subsurface_radius = get_value('Subsurface Radius')
        subsurface_color = get_value('Subsurface Color')
        metalness = get_value('Metallic')
        specular = get_value('Specular')
        anisotropic = get_value('Anisotropic')
        anisotropic_rotation = get_value('Anisotropic Rotation')
        clearcoat = get_value('Clearcoat')
        clearcoat_roughness = get_value('Clearcoat Roughness')
        sheen = get_value('Sheen')
        sheen_tint = get_value('Sheen Tint')
        transmission = get_value('Transmission')
        ior = get_value('IOR')
        transmission_roughness = get_value('Transmission Roughness')

        radius_scale = bpy.context.scene.unit_settings.scale_length * .01
        subsurface_radius = (subsurface_radius[0] * radius_scale,
                             subsurface_radius[1] * radius_scale,
                             subsurface_radius[2] * radius_scale,
                             1.0)
        # Cycles default value of 0.5 is equal to RPR weight of 1.0
        specular = (specular[0]*2, specular[0]*2, specular[0]*2, specular[0]*2)
        # Glass need PBR reflection type and disabled diffuse channel
        is_not_glass = True if metalness or not transmission else False

        null_vector = (0, 0, 0, 0)
        one_vector = (1.0, 1.0, 1.0, 1.0)
        key = self.id_data.name
        if not key:
            key = "Unnamed_{}".format(self)
        # Base color -> Diffuse (always on)
        rpr_mat = rpr_context.create_material(key, pyrprx.MATERIAL_UBER)

        if is_not_glass:
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_DIFFUSE_COLOR, base_color)
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, one_vector)
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_DIFFUSE_ROUGHNESS, roughness)
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, null_vector)
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, null_vector)
        else:
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_DIFFUSE_WEIGHT, null_vector)

        # Metallic -> Reflection (always on unless specular is set to non-physical 0.0)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_WEIGHT, specular)
        # mode 'metal' unless transmission is set and metallic is 0
        if is_not_glass:
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                                  pyrprx.UBER_MATERIAL_REFLECTION_MODE_METALNESS)
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_METALNESS, metalness)
        else:
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_MODE,
                                  pyrprx.UBER_MATERIAL_REFLECTION_MODE_PBR)
            rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_IOR, ior)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_COLOR, base_color)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_ROUGHNESS, roughness)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY, anisotropic)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFLECTION_ANISOTROPY_ROTATION, anisotropic_rotation)

        # Clearcloat -> Coating
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_COLOR, one_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_WEIGHT, clearcoat)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_ROUGHNESS, clearcoat_roughness)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_THICKNESS, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_TRANSMISSION_COLOR, null_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_MODE,
                              pyrprx.UBER_MATERIAL_COATING_MODE_PBR)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_COATING_IOR, ior)

        # Sheen -> Sheen
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SHEEN_WEIGHT, sheen)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SHEEN, base_color)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SHEEN_TINT, sheen_tint)

        # No Emission for Cycles Principled BSDF
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_EMISSION_WEIGHT, null_vector)

        # Subsurface -> Subsurface
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SSS_WEIGHT, subsurface)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SSS_SCATTER_COLOR, subsurface_color)
        # these also need to be set for core SSS to work.
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_BACKSCATTER_WEIGHT, subsurface)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_BACKSCATTER_COLOR, one_vector)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SSS_SCATTER_DISTANCE, subsurface_radius)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_SSS_MULTISCATTER, pyrpr.FALSE)

        # Transmission -> Refraction
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFRACTION_WEIGHT, transmission)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFRACTION_COLOR, base_color)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFRACTION_ROUGHNESS, transmission_roughness)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFRACTION_IOR, ior)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFRACTION_THIN_SURFACE, pyrpr.FALSE)
        rpr_mat.set_parameter(pyrprx.UBER_MATERIAL_REFRACTION_CAUSTICS, pyrpr.TRUE)

        return rpr_mat

    @classmethod
    def register(cls):
        log("Material: Register")
        bpy.types.Material.rpr = bpy.props.PointerProperty(
            name="RPR Material Settings",
            description="RPR material settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Material: Unregister")
        del bpy.types.Material.rpr


class RPR_MATERIAL_PT_material(RPR_Panel):
    bl_idname = 'rpr_material_PT_properties'
    bl_label = "RPR Settings"
    bl_context = 'material'

    @classmethod
    def poll(cls, context):
        return context.material

    def draw(self, context):
        layout = self.layout

        mat = context.material
        layout.operator('rpr.use_material_shading_nodes', icon='NODETREE')


class RPR_MATERIAL_PT_context(RPR_Panel):
    bl_label = ""
    bl_context = "material"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        if context.active_object and context.active_object.type == 'GPENCIL':
            return False
        else:
            return (context.material or context.object) and RPR_Panel.poll(context)

    def draw(self, context):
        layout = self.layout

        material = context.material
        object = context.object
        slot = context.material_slot
        space = context.space_data

        if object:
            is_sortable = len(object.material_slots) > 1
            rows = 1
            if is_sortable:
                rows = 4

            row = layout.row()

            row.template_list("MATERIAL_UL_matslots", "", object, "material_slots", object, "active_material_index", rows=rows)

            col = row.column(align=True)
            col.operator("object.material_slot_add", icon='ADD', text="")
            col.operator("object.material_slot_remove", icon='REMOVE', text="")

            col.menu("MATERIAL_MT_specials", icon='DOWNARROW_HLT', text="")

            if is_sortable:
                col.separator()

                col.operator("object.material_slot_move", icon='TRIA_UP', text="").direction = 'UP'
                col.operator("object.material_slot_move", icon='TRIA_DOWN', text="").direction = 'DOWN'

            if object.mode == 'EDIT':
                row = layout.row(align=True)
                row.operator("object.material_slot_assign", text="Assign")
                row.operator("object.material_slot_select", text="Select")
                row.operator("object.material_slot_deselect", text="Deselect")

        split = layout.split(factor=0.65)

        if object:
            split.template_ID(object, "active_material", new="material.new")
            row = split.row()

            if slot:
                row.prop(slot, "link", text="")
            else:
                row.label()
        elif material:
            split.template_ID(space, "pin_id")
            split.separator()


class RPR_MATERIAL_PT_preview(RPR_Panel):
    bl_label = "Preview"
    bl_context = "material"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.material and RPR_Panel.poll(context)

    def draw(self, context):
        self.layout.template_preview(context.material)


def find_node_in_node_tree(tree, node_type):
    for node in tree.nodes:
        nt = getattr(node, "bl_idname", None)
        if nt == node_type:
            return node
    return None


def find_output_node_in_tree(tree):
    res = find_node_in_node_tree(tree, 'rpr_shader_node_output')
    if not res:
        # try cycles output node
        res = find_node_in_node_tree(tree, 'ShaderNodeOutputMaterial')
#    log("find_output_node_in_tree({}) {}".format(tree, res))
    return res


def find_rpr_output_node(tree):
    return find_node_in_node_tree(tree, 'rpr_shader_node_output')


def find_cycles_output_node(tree):
    return find_node_in_node_tree(tree, 'ShaderNodeOutputMaterial')


def panel_node_draw(layout, id_data, output_type, input_name):
    if not id_data.use_nodes:
        layout.operator("rpr.use_material_shading_nodes", icon='NODETREE')
        return False

    node_tree = id_data.node_tree

#    node = node_tree.get_output_node('OUTPUT')
    node = find_output_node_in_tree(node_tree)
    if node:
        input = find_node_input(node, input_name)
        if input:
            layout.template_node_view(node_tree, node, input)
        else:
            layout.label(text="Incompatible output node")
    else:
        layout.label(text="No output node")

    return True


def node_tree_selector_draw(layout, material, output_type):
    if material and not material.node_tree:
        layout.operator("rpr.op_material_add_nodetree", icon='NODETREE')
    layout.separator()


def activate_shader_editor():
    activate_editor('RPRTreeType')
#    activate_editor('ShaderNodeTree')


def activate_editor(editor):
    if editor == '':
        return False
    nodeEditor = find_node_editor(editor)
    if nodeEditor:
        try:
            nodeEditor.tree_type = editor
        except:
            return False
    return True


def get_activate_editor_name():
    if bpy.context.screen:
        for area in bpy.context.screen.areas:
            if area.type == 'NODE_EDITOR':
                for space in area.spaces:
                    if space.type == 'NODE_EDITOR':
                        return space.tree_type
    return ''


def find_node_editor(tree_type):
    nodeEditor = None
    if bpy.context.screen:
        for area in bpy.context.screen.areas:
            if area.type == 'NODE_EDITOR':
                for space in area.spaces:
                    if space.type == 'NODE_EDITOR':
                        if space.tree_type == tree_type:
                            return None
                        else:
                            nodeEditor = space
    return nodeEditor


class RPR_MATERIAL_PT_surface(RPR_Panel):
    bl_label = "Surface"
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        return context.material and RPR_Panel.poll(context)

    def draw(self, context):
        layout = self.layout

        mat = context.material
        if not panel_node_draw(layout, mat, 'OUTPUT_MATERIAL', 'Surface'):
            layout.prop(mat, "diffuse_color")
