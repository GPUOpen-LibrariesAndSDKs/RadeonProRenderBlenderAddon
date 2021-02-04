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


class RPR_OBJECT_PT_object(RPR_Panel):
    bl_label = "RPR Settings"
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object and \
               context.object.type in ('MESH', 'CURVE', 'FONT', 'SURFACE', 'META') and \
               super().poll(context)

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr = context.object.rpr

        self.layout.prop(rpr, 'shadowcatcher')
        self.layout.prop(rpr, 'reflection_catcher')
        col = self.layout.column()

        col.prop(rpr, 'portal_light')
        col.enabled = context.scene.rpr.render_quality == 'FULL'  # Portal Lights are not supported in RPR2 yet

        col = self.layout.column()
        col.active = context.scene.render.use_motion_blur
        col.prop(rpr, "motion_blur")


class RPR_OBJECT_PT_visibility(RPR_Panel):
    bl_label = "Visibility"
    bl_parent_id = 'RPR_OBJECT_PT_object'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr = context.object.rpr
        cycles_vis = context.object.cycles_visibility

        flow = self.layout.grid_flow(row_major=True, even_columns=True)
        flow.column().prop(cycles_vis, 'camera')
        flow.column().prop(cycles_vis, 'glossy')
        flow.column().prop(cycles_vis, 'transmission')
        flow.column().prop(cycles_vis, 'diffuse')
        flow.column().prop(cycles_vis, 'shadow')
        flow.column().prop(rpr, 'visibility_contour')


class RPR_OBJECT_PT_subdivision(RPR_Panel):
    bl_label = "Subdivision"
    bl_parent_id = 'RPR_OBJECT_PT_object'

    def draw_header(self, context):
        row = self.layout.row()
        row.enabled = context.scene.rpr.render_quality in ('FULL', 'FULL2')
        row.prop(context.object.rpr, 'subdivision', text="")

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr = context.object.rpr

        col = self.layout.column()
        col.enabled = rpr.subdivision and context.scene.rpr.render_quality in ('FULL', 'FULL2')
        if context.scene.rpr.render_quality == 'FULL2':
            col.prop(rpr, 'subdivision_level')
        else:
            col.prop(rpr, 'subdivision_factor')
        col.prop(rpr, 'subdivision_crease_weight')
        col.prop(rpr, 'subdivision_boundary_type')
