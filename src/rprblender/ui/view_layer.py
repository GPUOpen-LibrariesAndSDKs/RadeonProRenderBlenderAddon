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


class RPR_VIEWLAYER_PT_aovs(RPR_Panel):
    bl_label = "RPR Passes"
    bl_context = 'view_layer'

    def draw(self, context):
        view_layer = context.view_layer.rpr
        row = self.layout.split(factor=0.5, align=True)

        col1 = row.column()
        col2 = row.column()
        for i in range(len(view_layer.enable_aovs)):
            aov = view_layer.aovs_info[i]
            if aov['name'] == "Combined":
                # not displaying "Combined" pass as it is always enabled by Blender
                continue

            col = col1 if i <= (len(view_layer.enable_aovs) // 2) + 1 else col2
            r = col.row()
            r.prop(view_layer, 'enable_aovs', index=i, text=aov['name'])

        col2.prop(view_layer, 'crytomatte_aov_object')
        col2.prop(view_layer, 'crytomatte_aov_material')


class RPR_RENDER_PT_denoiser(RPR_Panel):
    bl_label = "RPR Denoiser"
    bl_context = 'view_layer'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(context.view_layer.rpr.denoiser, 'enable', text="")

    def draw(self, context):
        ''' if this is macOS and 2.81+ use the builtin Blender denoiser '''
        
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        denoiser = context.view_layer.rpr.denoiser

        col = self.layout.column()
        col.enabled = denoiser.enable
        col.active = denoiser.is_available(context.scene)
        col.prop(denoiser, 'filter_type')

        if denoiser.filter_type == 'BILATERAL':
            col.prop(denoiser, "radius")
            col.prop(denoiser, 'color_sigma', slider=True)
            col.prop(denoiser, 'normal_sigma', slider=True)
            col.prop(denoiser, 'p_sigma', slider=True)
            col.prop(denoiser, 'trans_sigma', slider=True)

        elif denoiser.filter_type == 'EAW':
            col.prop(denoiser, 'color_sigma', slider=True)
            col.prop(denoiser, 'normal_sigma', slider=True)
            col.prop(denoiser, 'depth_sigma', slider=True)
            col.prop(denoiser, 'trans_sigma', slider=True)

        elif denoiser.filter_type == 'LWR':
            col.prop(denoiser, 'samples', slider=True)
            col.prop(denoiser, 'half_window', slider=True)
            col.prop(denoiser, 'bandwidth', slider=True)

        elif denoiser.filter_type == 'ML':
            col.prop(denoiser, 'ml_color_only')
            col.prop(denoiser, 'ml_use_fp16_compute_type')

        else:
            raise TypeError("No such filter type: %s" % denoiser.filter_type)


class RPR_RENDER_PT_override(RPR_Panel):
    """ Display View Layer material Override from Cycles """
    bl_label = "Override"
    bl_options = {'DEFAULT_CLOSED'}
    bl_context = "view_layer"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        view_layer = context.view_layer

        layout.prop(view_layer, "material_override")


class RPR_RENDER_PT_contour_rendering(RPR_Panel):
    bl_label = "Outline Rendering"
    bl_options = {'DEFAULT_CLOSED'}
    bl_context = "view_layer"

    def draw_header(self, context):
        self.layout.prop(context.view_layer.rpr, 'use_contour_render', text="")
        self.layout.enabled = context.scene.rpr.final_render_mode == 'FULL2'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        contour_settings = context.view_layer.rpr.contour

        main_column = self.layout.column()
        main_column.enabled = context.view_layer.rpr.use_contour_render and context.scene.rpr.final_render_mode == 'FULL2'

        col = main_column.column(align=True)
        col.prop(contour_settings, 'use_object_id')
        args = col.column(align=True)
        args.enabled = contour_settings.use_object_id
        args.prop(contour_settings, 'object_id_line_width', slider=True)

        col = main_column.column(align=True)
        col.prop(contour_settings, 'use_material_id')
        args = col.column(align=True)
        args.enabled = contour_settings.use_material_id
        args.prop(contour_settings, 'material_id_line_width', slider=True)

        col = main_column.column(align=True)
        col.prop(contour_settings, 'use_shading_normal')
        args = col.column(align=True)
        args.enabled = contour_settings.use_shading_normal
        args.prop(contour_settings, 'normal_threshold', slider=True)
        args.prop(contour_settings, 'shading_normal_line_width', slider=True)

        col = main_column.column(align=True)
        col.prop(contour_settings, 'antialiasing', slider=True)

        col = main_column.column(align=True)
        col.prop(contour_settings, 'use_uv')
        args = col.column(align=True)
        args.enabled = contour_settings.use_uv
        args.prop(contour_settings, 'uv_line_width', slider=True)
        args.prop(contour_settings, 'uv_threshold', slider=True)
        args.prop(contour_settings, 'use_uv_secondary')
