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
import bpy

from . import RPR_Panel


class RPR_VIEW3D_MT_menu(bpy.types.Menu):
    bl_label = "RPR"
    bl_idname = 'RPR_VIEW3D_MT_menu'

    def draw(self, context):
        layout = self.layout
        layout.prop_menu_enum(context.scene.rpr, 'render_mode')


class RPR_VIEW3D_PT_panel(RPR_Panel):
    bl_label = "RPR"
    bl_space_type = 'VIEW_3D'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        rpr = context.scene.rpr

        if len(rpr.render_quality_items) > 1:
            layout.prop(rpr, 'render_quality')

        row = layout.row()
        row.enabled = len(rpr.render_quality_items) > 1
        row.prop(rpr, 'render_mode')


def draw_menu(self, context):
    """ Draws 'RPR' menu item if RPR engine is active """
    if context.engine == 'RPR':
        layout = self.layout
        layout.popover('RPR_VIEW3D_PT_panel')
