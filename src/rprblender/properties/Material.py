import bpy
from bpy.types import Operator
from bpy_extras.node_utils import find_node_input

from . import RPR_Panel, RPR_Properties
from rprblender import logging, engine

import pyrpr
import pyrprx


ShaderTypeUber2 = 0xFF


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
        logging.info("Enabling nodes for {}".format(context))
        if context.material:
            context.material.use_nodes = True

        return {'FINISHED'}


class RPR_MATERIAL_parser(RPR_Properties):
    def sync(self, rpr_context) -> pyrprx.Material:
        mat = self.id_data
        logging.info("Syncing material: %s" % mat.name)
        key = mat.as_pointer()
        tree = mat.get('node_tree', None)

        color = (0.8, 0.5, 0.5, 1.0)
        if not tree:
            # "ERROR" shader color
            color = (1.0, 0.0, 1.0, 1.0)
            #return None

        # Fake material for tests
        null_vector = (0, 0, 0, 0)
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

    @classmethod
    def register(cls):
        logging.info("Material: Register")
        bpy.types.Material.rpr = bpy.props.PointerProperty(
            name="RPR Material Settings",
            description="RPR material settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        logging.info("Material: Unregister")
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
#    logging.info("find_output_node_in_tree({}) {}".format(tree, res), tag='material')
    return res


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


classes_to_register = (
    RPR_MATERIAL_OT_UseShadingNodes, RPR_MATERIAL_parser,
    RPR_MATERIAL_PT_context, RPR_MATERIAL_PT_preview, RPR_MATERIAL_PT_material, RPR_MATERIAL_PT_surface
)
