#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
from bpy_extras.node_utils import find_node_input

from . import RPR_Panel
from rprblender.export.material import get_material_output_node


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

            col.menu("MATERIAL_MT_context_menu", icon='DOWNARROW_HLT', text="")

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


class RPR_MaterialOutputSocket(RPR_Panel):
    bl_label = ""
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        return context.material and super().poll(context)

    def draw(self, context):
        layout = self.layout

        node_tree = context.material.node_tree

        output_node = get_material_output_node(context.material)
        if not output_node:
            layout.label(text="No output node")
            return

        input = output_node.inputs[self.bl_label]
        layout.template_node_view(node_tree, output_node, input)


class RPR_MATERIAL_PT_surface(RPR_MaterialOutputSocket):
    bl_label = "Surface"

    def draw(self, context):
        layout = self.layout

        node_tree = context.material.node_tree

        output_node = get_material_output_node(context.material)
        if not output_node:
            layout.label(text="No output node")
            return

        # check for Principled BSDF
        if output_node and "Surface" in output_node.inputs:
            surface_socket = output_node.inputs['Surface']
            if surface_socket.is_linked and \
                surface_socket.links[0].from_node.bl_idname == 'ShaderNodeBsdfPrincipled':
                layout.operator('rpr.principled_to_uber')

        input = output_node.inputs[self.bl_label]
        layout.template_node_view(node_tree, output_node, input)


class RPR_MATERIAL_PT_displacement(RPR_MaterialOutputSocket):
    bl_label = "Displacement"

    def draw(self, context):
        layout = self.layout

        layout.prop(context.material.cycles, 'displacement_method')
        super().draw(context)


class RPR_MATERIAL_PT_volume(RPR_MaterialOutputSocket):
    bl_label = "Volume"


class RPR_MATERIAL_PT_node_arrange(RPR_Panel):
    bl_label = "RPR Node Arrange"
    bl_context = "material"
    bl_options = {'DEFAULT_CLOSED'}
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.active_material and RPR_Panel.poll(context)

    def draw(self, context):
        self.layout.operator('rpr.arrange_material_nodes', text='Arrange')


class RPR_MATERIAL_PT_node_bake(RPR_Panel):
    bl_label = "RPR Node Bake"
    bl_context = "material"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context):
        return context.active_object and\
               context.active_object.type == 'MESH' and\
               len(context.selected_objects) == 1 and\
               context.active_object in context.selected_objects and\
               context.active_object.active_material and\
               context.active_object.active_material.use_nodes and\
               RPR_Panel.poll(context)

    def draw(self, context):
        self.layout.operator('rpr.bake_selected_nodes', text='Bake Selected Nodes')
