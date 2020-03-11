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
from . import RPR_Panel

from rprblender.operators.world import FOG_KEY
from rprblender.export.material import get_material_input_node


class RPR_WORLD_PT_environment(RPR_Panel):
    bl_label = "Environment Light"
    bl_space_type = "PROPERTIES"
    bl_context = 'world'

    def draw_header(self, context):
        self.layout.prop(context.scene.world.rpr, 'enabled', text="")

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        rpr = context.scene.world.rpr

        layout.enabled = rpr.enabled

        layout.prop(rpr, 'intensity')
        layout.separator()

        row = layout.row()
        row.use_property_split = False
        row.prop(rpr, 'mode', expand=True)

        if rpr.mode == 'IBL':
            ibl = rpr.ibl

            layout.template_ID(ibl, "image", open="image.open")

            row = layout.row()
            row.enabled = ibl.image is None
            row.prop(ibl, 'color')

        else:
            sun_sky = rpr.sun_sky

            col = layout.column(align=True)
            col.prop(sun_sky, 'azimuth')
            col.prop(sun_sky, 'altitude')

            layout.prop(sun_sky, 'resolution')


class RPR_EnvironmentOverride(RPR_Panel):
    bl_parent_id = 'RPR_WORLD_PT_environment'
    bl_options = {'DEFAULT_CLOSED'}

    type = ''

    def draw_header(self, context):
        rpr = context.scene.world.rpr
        row = self.layout.row()
        row.enabled = rpr.enabled
        row.prop(rpr, f'{self.type}_override', text="")

    def draw(self, context):
        rpr = context.scene.world.rpr

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.enabled = rpr.enabled and getattr(rpr, f'{self.type}_override')

        layout.template_ID(rpr, f'{self.type}_image', open='image.open')

        row = layout.row()
        row.enabled = getattr(rpr, f'{self.type}_image') is None
        row.prop(rpr, f'{self.type}_color')


class RPR_WORLD_PT_background_override(RPR_EnvironmentOverride):
    bl_label = "Background Override"
    type = 'background'

    def draw(self, context):
        rpr = context.scene.world.rpr
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.enabled = rpr.background_override

        row = layout.row()
        row.use_property_split = False
        row.prop(rpr, 'background_image_type', expand=True)

        layout.template_ID(rpr, 'background_image', open='image.open', new='image.new')

        row = layout.row()
        row.enabled = rpr.background_image is None
        row.prop(rpr, 'background_color')


class RPR_WORLD_PT_reflection_override(RPR_EnvironmentOverride):
    bl_label = "Reflection Override"
    type = 'reflection'


class RPR_WORLD_PT_refraction_override(RPR_EnvironmentOverride):
    bl_label = "Refraction Override"
    type = 'refraction'


class RPR_WORLD_PT_transparency_override(RPR_EnvironmentOverride):
    bl_label = "Transparency Override"
    type = 'transparency'


class RPR_WORLD_PT_gizmo(RPR_Panel):
    bl_label = "Gizmo"
    bl_parent_id = 'RPR_WORLD_PT_environment'

    def draw(self, context):
        rpr = context.scene.world.rpr

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.enabled = rpr.enabled

        layout.prop(rpr, 'gizmo_rotation')


class RPR_WORLD_PT_sun_sky(RPR_Panel):
    bl_label = "Sun & Sky Properties"
    bl_parent_id = 'RPR_WORLD_PT_environment'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return super().poll(context) and context.scene.world.rpr.mode == 'SUN_SKY'

    def draw(self, context):
        rpr = context.scene.world.rpr
        sun_sky = rpr.sun_sky

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.enabled = rpr.enabled

        flow = layout.grid_flow(row_major=True, even_columns=True)

        col = flow.column(align=True)
        col.prop(sun_sky, 'turbidity')
        col.prop(sun_sky, 'sun_glow')
        col.prop(sun_sky, 'sun_disc')

        col = flow.column(align=True)
        col.prop(sun_sky, 'saturation')
        col.prop(sun_sky, 'horizon_height')
        col.prop(sun_sky, 'horizon_blur')

        col = flow.column(align=True)
        col.prop(sun_sky, 'filter_color')
        col.prop(sun_sky, 'ground_color')


class RPR_WORLD_PT_fog(RPR_Panel):
    bl_label = "Fog"
    bl_space_type = "PROPERTIES"
    bl_context = 'world'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        fog_object = context.scene.objects.get(FOG_KEY)
        if not fog_object:
            layout.operator('rpr.op_create_fog_object')
            return

        col = layout.column()
        col.enabled = False
        col.prop(fog_object, 'name', text="Fog Object")

        if not fog_object.data.materials:
            layout.label(text="Incorrect fog material")
            return

        mat = fog_object.data.materials[0]
        volume_node = get_material_input_node(mat, 'Volume')
        if not volume_node or volume_node.bl_idname != 'ShaderNodeVolumePrincipled':
            layout.label(text="Incorrect fog material")
            return

        col = layout.column(align=True)
        col.template_node_view(mat.node_tree, volume_node, volume_node.inputs['Color'])
        col.template_node_view(mat.node_tree, volume_node, volume_node.inputs['Density'])
        col.template_node_view(mat.node_tree, volume_node, volume_node.inputs['Anisotropy'])
        col.template_node_view(mat.node_tree, volume_node, volume_node.inputs['Absorption Color'])
