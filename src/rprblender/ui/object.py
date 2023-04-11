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
from rprblender.utils import BLENDER_VERSION


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
        col.active = context.scene.render.use_motion_blur
        col.prop(rpr, "motion_blur")
        col.prop(rpr, "deformation_blur")


class RPR_OBJECT_PT_visibility(RPR_Panel):
    bl_label = "Visibility"
    bl_parent_id = 'RPR_OBJECT_PT_object'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        obj = context.object

        if BLENDER_VERSION >= '3.0':
            self.layout.prop(obj, 'visible_camera', text="Camera")
            self.layout.prop(obj, 'visible_diffuse', text="Diffuse")
            self.layout.prop(obj, 'visible_glossy', text="Glossy")
            self.layout.prop(obj, 'visible_transmission', text="Transmission")
            self.layout.prop(obj, 'visible_shadow', text="Shadow")

        else:
            visibility = obj.cycles_visibility

            self.layout.prop(visibility, 'camera')
            self.layout.prop(visibility, 'diffuse')
            self.layout.prop(visibility, 'glossy')
            self.layout.prop(visibility, 'transmission')
            self.layout.prop(visibility, 'shadow')

        self.layout.prop(obj.rpr, 'shadow_color')
        self.layout.prop(obj.rpr, 'receive_shadow')
        self.layout.prop(obj.rpr, 'visibility_contour')


class RPR_OBJECT_PT_subdivision(RPR_Panel):
    bl_label = "Subdivision"
    bl_parent_id = 'RPR_OBJECT_PT_object'

    def draw_header(self, context):
        row = self.layout.row()
        row.prop(context.object.rpr, 'subdivision', text="")

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr = context.object.rpr

        col = self.layout.column()
        col.prop(rpr, 'subdivision_level')
        col.prop(rpr, 'subdivision_factor')
        col.prop(rpr, 'subdivision_crease_weight')
        col.prop(rpr, 'subdivision_boundary_type')
