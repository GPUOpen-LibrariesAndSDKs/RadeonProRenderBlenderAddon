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

        if len(pyrpr.Context.gpu_devices) == 0:
            col = layout.column(align=True)
            row = col.row()
            row.enabled = False
            row.prop(devices, 'cpu_state')
            col.prop(devices, 'cpu_threads')

        else:
            if pyrpr.Context.cpu_device:
                col = layout.column(align=True)
                col.prop(devices, 'cpu_state')
                row = col.row()
                row.enabled = devices.cpu_state
                row.prop(devices, 'cpu_threads')

                layout.separator()

            col = layout.column(align=True)
            for i in range(len(devices.gpu_states)):
                col.prop(devices, 'gpu_states', index=i, text=pyrpr.Context.gpu_devices[i]['name'])


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

        if len(pyrpr.Context.gpu_devices) == 0:
            col = layout.column(align=True)
            row = col.row()
            row.enabled = False
            row.prop(devices, 'cpu_state')
            col.prop(devices, 'cpu_threads')

        else:
            if pyrpr.Context.cpu_device:
                col = layout.column(align=True)
                col.prop(devices, 'cpu_state')
                row = col.row()
                row.enabled = devices.cpu_state
                row.prop(devices, 'cpu_threads')

                layout.separator()

            col = layout.column(align=True)
            for i in range(len(devices.gpu_states)):
                col.prop(devices, 'gpu_states', index=i, text=pyrpr.Context.gpu_devices[i]['name'])


class RPR_RENDER_PT_limits(RPR_Panel):
    bl_label = "Sampling"
    bl_context = 'render'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        limits = context.scene.rpr.limits

        enable_adaptive = context.scene.rpr.get_devices(True).count() == 1

        col = self.layout.column(align=True)
        row = col.row()
        row.enabled = enable_adaptive
        row.prop(limits, 'min_samples')
        col.prop(limits, 'max_samples')
        row = col.row()
        row.enabled = enable_adaptive
        row.prop(limits, 'noise_threshold', slider = True)
        col.prop(limits, 'update_samples')

        col = self.layout.column(align=True)
        col.enabled = not context.scene.rpr.use_tile_render
        col.prop(limits, 'seconds')

        col = self.layout.column(align=True)
        col.prop(context.scene.rpr, 'use_tile_render')

        col = col.column(align=True)
        col.enabled = context.scene.rpr.use_tile_render
        col.prop(context.scene.rpr, 'tile_x')
        col.prop(context.scene.rpr, 'tile_y')
        col.prop(context.scene.rpr, 'tile_order')


class RPR_RENDER_PT_viewport_limits(RPR_Panel):
    bl_label = "Viewport & Preview Sampling"
    bl_parent_id = 'RPR_RENDER_PT_limits'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        limits = context.scene.rpr.viewport_limits

        enable_adaptive = context.scene.rpr.get_devices(False).count() == 1

        col = self.layout.column(align=True)
        row = col.row()
        row.enabled = enable_adaptive
        row.prop(limits, 'min_samples')
        col.prop(limits, 'max_samples')
        row = col.row()
        row.enabled = enable_adaptive
        row.prop(limits, 'noise_threshold', slider = True)
        col.prop(limits, 'limit_viewport_resolution')

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

        if pyhybrid.enabled:
            self.layout.prop(context.scene.rpr, 'render_quality')


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
        col.prop(context.scene.camera.data.rpr, 'motion_blur_exposure', text="Camera Exposure", slider=True)


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
        label_center(col, "%s for Blender %d.%d.%d (core %s)" % (
            bl_info['name'], version[0], version[1], version[2], utils.core_ver_str()
        ))
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
