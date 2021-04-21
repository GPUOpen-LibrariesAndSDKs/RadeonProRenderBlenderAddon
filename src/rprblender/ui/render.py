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
import pyrpr
import pyhybrid

from . import RPR_Panel
from rprblender import bl_info
from rprblender import utils
from rprblender.utils.user_settings import get_user_settings


class RPR_RENDER_PT_devices(RPR_Panel):
    bl_label = "Render Devices"
    bl_context = 'render'

    def draw(self, context):
        settings = get_user_settings()
        devices = settings.final_devices

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        if not pyrpr.Context.gpu_devices:
            col = layout.column(align=True)
            row = col.row()
            row.enabled = False
            row.prop(devices, 'cpu_state', text=pyrpr.Context.cpu_device['name'])
            col.prop(devices, 'cpu_threads')

        else:
            if pyrpr.Context.cpu_device:
                col = layout.column(align=True)
                col.enabled = context.scene.rpr.render_quality in ('FULL', 'FULL2')

                col.prop(devices, 'cpu_state', text=pyrpr.Context.cpu_device['name'])
                row = col.row()
                row.enabled = devices.cpu_state
                row.prop(devices, 'cpu_threads')

                layout.separator()

            col = layout.column(align=True)
            for i, gpu_device in enumerate(pyrpr.Context.gpu_devices):
                col.prop(devices, 'gpu_states', index=i, text=gpu_device['name'])


class RPR_RENDER_PT_viewport_devices(RPR_Panel):
    bl_label = "Separate Viewport & Preview Devices"
    bl_parent_id = 'RPR_RENDER_PT_devices'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return super().poll(context) and len(pyrpr.Context.gpu_devices) > 0

    def draw_header(self, context):
        settings = get_user_settings()
        self.layout.prop(settings, "separate_viewport_devices", text="")
        self.layout.active = settings.separate_viewport_devices

    def draw(self, context):
        settings = get_user_settings()
        devices = settings.viewport_devices

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        self.layout.enabled = settings.separate_viewport_devices

        if not pyrpr.Context.gpu_devices:
            col = layout.column(align=True)
            row = col.row()
            row.enabled = False
            row.prop(devices, 'cpu_state', text=pyrpr.Context.cpu_device['name'])
            col.prop(devices, 'cpu_threads')

        else:
            if pyrpr.Context.cpu_device:
                col = layout.column(align=True)
                col.enabled = context.scene.rpr.render_quality in ('FULL', 'FULL2')

                col.prop(devices, 'cpu_state', text=pyrpr.Context.cpu_device['name'])
                row = col.row()
                row.enabled = devices.cpu_state
                row.prop(devices, 'cpu_threads')

                layout.separator()

            col = layout.column(align=True)
            for i, gpu_device in enumerate(pyrpr.Context.gpu_devices):
                col.prop(devices, 'gpu_states', index=i, text=gpu_device['name'])


class RPR_RENDER_PT_limits(RPR_Panel):
    bl_label = "Sampling"
    bl_context = 'render'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr = context.scene.rpr
        limits = rpr.limits

        col = self.layout.column(align=True)
        row = col.row()
        row.prop(limits, 'min_samples')
        col.prop(limits, 'max_samples')
        row = col.row()
        row.prop(limits, 'noise_threshold', slider=True)
        
        col = self.layout.column(align=True)
        col.enabled = not rpr.is_tile_render_available
        col.prop(limits, 'seconds')

        col = self.layout.column(align=True)
        col.enabled = rpr.render_quality in ('FULL', 'FULL2')
        col.prop(rpr, 'use_tile_render')

        col = col.column(align=True)
        col.enabled = rpr.is_tile_render_available
        col.prop(rpr, 'tile_x')
        col.prop(rpr, 'tile_y')
        col.prop(rpr, 'tile_order')


class RPR_RENDER_PT_viewport_limits(RPR_Panel):
    bl_label = "Viewport & Preview Sampling"
    bl_parent_id = 'RPR_RENDER_PT_limits'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        limits = context.scene.rpr.viewport_limits
        settings = get_user_settings()

        col = self.layout.column(align=True)
        row = col.row()
        row.prop(limits, 'min_samples')
        col.prop(limits, 'max_samples')
        row = col.row()
        row.prop(limits, 'noise_threshold', slider=True)
        if context.scene.rpr.render_quality == 'FULL2':
            row.enabled = False

        adapt_resolution = context.scene.rpr.render_quality in ('FULL', 'FULL2')
        col1 = col.column()
        col1.enabled = adapt_resolution
        col1.prop(settings, 'adapt_viewport_resolution')

        col1 = col.column(align=True)
        col1.enabled = settings.adapt_viewport_resolution and adapt_resolution
        col1.prop(settings, 'viewport_samples_per_sec', slider=True)
        col1.prop(settings, 'min_viewport_resolution_scale', slider=True)

        col.prop(settings, 'use_gl_interop')

        col.prop(settings, 'viewport_denoiser_upscale')

        col.separator()
        col.prop(limits, 'preview_samples')
        col.prop(limits, 'preview_update_samples')


class RPR_RENDER_PT_quality(RPR_Panel):
    """ This is a parent Panel for (RPR_RENDER_PT_max_ray_depth, RPR_RENDER_PT_light_clamping)"""

    bl_label = "Quality"
    bl_context = 'render'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr = context.scene.rpr

        if len(rpr.render_quality_items) > 1:
            self.layout.prop(rpr, 'render_quality')
        
        if rpr.render_quality in ('LOW', 'MEDIUM', 'HIGH'):
            self.layout.prop(rpr, 'hybrid_low_mem')

        if rpr.render_quality == 'FULL2':
            self.layout.prop(rpr, texture_compression)


class RPR_RENDER_PT_max_ray_depth(RPR_Panel):
    bl_label = "Max Ray Depth"
    bl_parent_id = 'RPR_RENDER_PT_quality'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr_scene = context.scene.rpr

        self.layout.prop(rpr_scene, 'max_ray_depth', slider=True)

        col = self.layout.column(align=True)
        col.prop(rpr_scene, 'diffuse_depth', slider=True)
        col.prop(rpr_scene, 'glossy_depth', slider=True)
        col.prop(rpr_scene, 'refraction_depth', slider=True)
        col.prop(rpr_scene, 'glossy_refraction_depth', slider=True)
        col.prop(rpr_scene, 'shadow_depth', slider=True)

        self.layout.prop(rpr_scene, 'ray_cast_epsilon', slider=True)


class RPR_RENDER_PT_contour_rendering(RPR_Panel):
    bl_label = "Contour Rendering"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(context.scene.rpr, 'use_contour_render', text="")
        self.layout.enabled = context.scene.rpr.render_quality == 'FULL2'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr_scene = context.scene.rpr

        main_column = self.layout.column()
        main_column.enabled = context.scene.rpr.is_contour_used()

        col = main_column.column(align=True)
        col.prop(rpr_scene, 'contour_use_object_id')
        args = col.column(align=True)
        args.enabled = rpr_scene.contour_use_object_id
        args.prop(rpr_scene, 'contour_object_id_line_width', slider=True)

        col = main_column.column(align=True)
        col.prop(rpr_scene, 'contour_use_material_id')
        args = col.column(align=True)
        args.enabled = rpr_scene.contour_use_material_id
        args.prop(rpr_scene, 'contour_material_id_line_width', slider=True)

        col = main_column.column(align=True)
        col.prop(rpr_scene, 'contour_use_shading_normal')
        args = col.column(align=True)
        args.enabled = rpr_scene.contour_use_shading_normal
        args.prop(rpr_scene, 'contour_normal_threshold', slider=True)
        args.prop(rpr_scene, 'contour_shading_normal_line_width', slider=True)

        col = main_column.column(align=True)
        col.prop(rpr_scene, 'contour_antialiasing', slider=True)

        main_column.prop(rpr_scene, 'contour_debug_flag')


class RPR_RENDER_PT_bake_textures(RPR_Panel):
    bl_label = "Node Baking"
    bl_parent_id = 'RPR_RENDER_PT_quality'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        settings = get_user_settings()

        self.layout.prop(settings, 'bake_resolution')
        self.layout.operator('rpr.bake_all_nodes')


class RPR_RENDER_PT_pixel_filter(RPR_Panel):
    bl_label = "Pixel Filter"
    bl_parent_id = 'RPR_RENDER_PT_quality'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr_scene = context.scene.rpr

        col = self.layout.column()
        col.prop(rpr_scene, 'pixel_filter')
        col.prop(rpr_scene, 'pixel_filter_width')


class RPR_RENDER_PT_light_clamping(RPR_Panel):
    bl_label = "Clamping"
    bl_parent_id = 'RPR_RENDER_PT_quality'

    def draw_header(self, context):
        self.layout.prop(context.scene.rpr, 'use_clamp_radiance', text="")

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr_scene = context.scene.rpr

        col = self.layout.column()
        col.enabled = rpr_scene.use_clamp_radiance
        col.prop(rpr_scene, 'clamp_radiance')


class RPR_RENDER_PT_render_stamp(RPR_Panel):
    bl_label = "Render Stamp"
    bl_context = 'render'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        # Hide panel for non-Windows OS
        return super().poll(context) and utils.IS_WIN

    def draw_header(self, context):
        self.layout.prop(context.scene.rpr, 'use_render_stamp', text="")

    def draw(self, context):
        layout = self.layout

        col = layout.column()
        col.enabled = context.scene.rpr.use_render_stamp
        col.prop(context.scene.rpr, 'render_stamp', text="")


class RPR_RENDER_PT_motion_blur(RPR_Panel):
    bl_label = "Motion Blur"
    bl_context = 'render'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(context.scene.render, 'use_motion_blur', text="")

    def draw(self, context):
        layout = self.layout

        layout.use_property_split = True
        layout.use_property_decorate = False

        if not context.scene.camera:
            layout.label(text="No active camera")
            return

        col = layout.column()
        col.enabled = context.scene.render.use_motion_blur
        col.prop(context.scene.camera.data.rpr, 'motion_blur_exposure', text="Shutter Opening ratio", slider=True)

        col = layout.column()
        col.enabled = context.scene.render.use_motion_blur and context.scene.rpr.render_quality == 'FULL2'
        col.prop(context.scene.rpr, "motion_blur_in_velocity_aov")


class RPR_RENDER_PT_film_transparency(RPR_Panel):
    bl_label = "Film"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        scene = context.scene

        layout.prop(scene.render, "film_transparent", text="Transparent Background")


class RPR_RENDER_PT_help_about(RPR_Panel):
    ''' Help/About UI panel '''

    bl_label = "Help/About"
    bl_context = 'render'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        def label_center(lay, text):
            row = lay.row()
            row.alignment = 'CENTER'
            row.label(text=text)

        layout = self.layout

        # Drawing info about plugin
        col = layout.column(align=True)
        version = bl_info['version']
        label_center(col, f"{bl_info['name']} for Blender {version[0]}.{version[1]}.{version[2]}")
        label_center(col, f"(core {utils.core_ver_str()}, RIF {utils.rif_ver_str()})")
        label_center(col, "© 2016 Advanced Micro Devices, Inc. (AMD)")
        label_center(col, "Portions of this software are created")
        label_center(col, "and copyrighted to other third parties.")

        # Drawing buttons to open web pages
        layout.separator()
        col = layout.column()
        row = col.row(align=True)
        row.alignment = 'CENTER'
        row.operator('rpr.op_open_web_page', text="Main Site").page = 'main_site'
        row.operator('rpr.op_open_web_page', text="Documentation").page = 'documentation'
        row.operator('rpr.op_open_web_page', text="Downloads").page = 'downloads'

        row = col.row(align=True)
        row.alignment = 'CENTER'
        row.operator('rpr.op_open_web_page', text="Community").page = 'community'
        row.operator('rpr.op_open_web_page', text="Bug Reports").page = 'bug_reports'


class RPR_RENDER_PT_debug(RPR_Panel):
    ''' Sub panel under Help/About panel with debug options '''

    bl_label = "Debug"
    bl_context = 'render'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        settings = get_user_settings()
        rpr = context.scene.rpr

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.prop(rpr, 'log_min_level')

        if utils.IS_WIN or utils.IS_MAC:
            layout.prop(settings, 'collect_stat')

        col = layout.column(align=True)
        col.prop(rpr, 'trace_dump')
        row = col.row()
        row.enabled = rpr.trace_dump
        row.use_property_split = False
        row.prop(rpr, 'trace_dump_folder', text="")

        layout.row().prop(rpr, 'texture_cache_dir')
        layout.row().operator('rpr.op_clear_tex_cache', text='Clear Cache')

