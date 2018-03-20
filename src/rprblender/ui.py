#!python3
import bpy
import math
import platform
import rprblender
import pyrpr
import pyrpr_load_store
from pyrpr import ffi
from datetime import datetime
from bpy.types import Panel, Menu, Operator

from . import rpraddon
from .nodes import RPRPanel
from . import versions
from . import logging
from pathlib import Path
from bpy_extras.io_utils import ExportHelper
from rprblender.node_editor import shader_node_output_name, find_node
from rprblender.versions import get_render_passes_aov, is_blender_support_aov
from . import version_checking
from rprblender.helpers import isMetalOn

PANEL_WIDTH_FOR_COLUMN = 200

def create_ui_autosize_column(context, col, single=False):
    if context.region.width > PANEL_WIDTH_FOR_COLUMN:
        row = col.row()
        split = row.split(percentage=0.5)
        col1 = split.column(align=True)
        split = split.split()
        col2 = split.column(align=True)
        is_row = False
    else:
        col1 = col.row().column(align=True)
        if not single:
            col.separator()
        col2 = col.row().column(align=True)
        is_row = True
    return col1, col2, is_row


def createRoseShape():
    ro = 150.0
    ri = 50.0
    w = ro - ri
    rt = w * 1.0 / 3.33333333

    rose_points = [
        (0.0, ro),
        (27.0, rt),
        (45.0, ri),
        (63.0, rt),
        (90.0, ro),
        (117.0, rt),
        (135.0, ri),
        (153.0, rt),
        (180.0, ro),
        (207.0, rt),
        (225.0, ri),
        (243.0, rt),
        (270.0, ro),
        (297.0, rt),
        (315.0, ri),
        (333.0, rt),
        (0.0, ro)
    ]

    verteces = []
    for pt in rose_points:
        angle = math.radians(pt[0])
        x = pt[1] * math.cos(angle);
        y = pt[1] * math.sin(angle);
        verteces.append((x, y, 0))

    edges = []
    for i0 in range(len(rose_points)):
        i1 = i0 + 1 if i0 + 1 < len(rose_points) else 0
        edges.append((i0, i1))

    return verteces, edges

@rpraddon.register_class
class SelectIESLightData(bpy.types.Operator, ExportHelper):
    bl_idname = "rpr.op_select_ies_light_data"
    bl_label = "Load IES Light Data"

    filename_ext = ".ies"

    filter_glob = bpy.props.StringProperty(
        default="*.ies",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        context.lamp.rpr_lamp.ies_file_name = self.filepath
        return {'FINISHED'}

def draw_ies_light_select(self, lamp):
    row = self.layout.row()
    row.label('IES Data File:')
    row = self.layout.row(align=True)
    row.alignment = 'EXPAND'
    row.prop(lamp.rpr_lamp, "ies_file_name", text='')
    row.operator('rpr.op_select_ies_light_data', text='', icon='FILESEL')

def draw_lamp_settings(self, context):
    if context.scene.render.engine == 'RPR':
        lamp = context.lamp  # type: bpy.types.Lamp

        self.layout.prop(lamp, "type", expand=True)
        self.layout.prop(lamp.rpr_lamp, "intensity")
        self.layout.prop(lamp, "color")
        if 'AREA' == lamp.type:
            self.layout.prop(lamp, "shape", expand=True)
            if 'SQUARE' == lamp.shape:
                self.layout.prop(lamp, "size")
            else:
                self.layout.prop(lamp, "size", text='Width')
                self.layout.prop(lamp, "size_y", text='Height')

            draw_ies_light_select(self, lamp)
        elif 'SPOT' == lamp.type:
            self.layout.prop(lamp, "spot_size", text='Angle')
            self.layout.prop(lamp, "spot_blend", text='Blend')

        if lamp.type in ['POINT']:
            draw_ies_light_select(self, lamp)

########################################################################################################################
# Render panel
########################################################################################################################
def draw_settings(self, context):
    if context.scene.render.engine == 'RPR':
        self.layout.prop(get_render_passes_aov(context), "transparent")


from . import helpers


@rpraddon.register_class
class RPRRender_PT_render_resources(RPRPanel, Panel):
    bl_label = "RPR Render Resources"

    def draw(self, context):
        layout = self.layout
        settings = helpers.get_user_settings()
        if len(helpers.render_resources_helper.devices) > 0:
            # check non certified devices
            have_only_certified = True
            for i, device in enumerate(helpers.render_resources_helper.devices):
                if i >= helpers.RenderResourcesHelper.max_gpu_count:
                    break
                if not device['certified']:
                    have_only_certified = False

            gpu_enable = settings.device_type != "cpu"

            # ui draw
            col1, col2, is_row = create_ui_autosize_column(context, layout, True)

            col1.label('Device Type')
            col1.prop(settings, "device_type", text='')

            col1.prop(settings, "samples", slider=True)
            row = col1.row()
            row.enabled = gpu_enable
            row.prop(settings, "device_type_plus_cpu")

            if not is_row:
                col2.label('')
            col2.prop(settings, "gpu_count")
            col2.operator("rpr.op_gpu_list")
            col2.enabled = gpu_enable

            col = layout.column()
            if not have_only_certified:
                row = col.row()
                row.prop(settings, "include_uncertified_devices")
        else:
            layout.label("You haven't any compatibility GPU. Render using CPU only.")


@rpraddon.register_class
class RPRRender_PT_tonemapping(RPRPanel, Panel):
    bl_label = "RPR Tone Mapping"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(context.scene.rpr.render.tone_mapping, "enable", text='')

    def draw(self, context):
        layout = self.layout
        tm = context.scene.rpr.render.tone_mapping
        bar = layout.row() if context.region.width > PANEL_WIDTH_FOR_COLUMN else layout.column()
        bar.enabled = tm.enable
        bar.prop(tm, "type", expand=True)
        col1, col2, is_row = create_ui_autosize_column(context, layout, True)

        if tm.type == 'simplified':
            col1.prop(tm.simplified, "exposure")
            col2.prop(tm.simplified, "contrast")
        elif tm.type == 'linear':
            col1.prop(tm.linear, "iso")
            col1.prop(tm.linear, "f_stop")
            col2.prop(tm.linear, "shutter_speed")
        elif tm.type == 'non_linear':
            col1.prop(tm.nonlinear, "burn")
            col2.prop(tm.nonlinear, "prescale")
            col2.prop(tm.nonlinear, "postscale")


@rpraddon.register_class
class RPRRender_PT_white_balance(RPRPanel, Panel):
    bl_label = "RPR White Balance"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(context.scene.rpr.render.white_balance, "enable", text='')

    def draw(self, context):
        layout = self.layout
        settings = context.scene.rpr.render.white_balance
        col = layout.column()
        col.enabled = settings.enable
        row = col.row()

        row.alignment = 'EXPAND'
        split = row.split(percentage=0.85, align=True)
        col1 = split.column(align=True)
        col1.prop(settings, "color_temperature", )
        col1 = split.column(align=True)
        col1.prop(settings, "preview_color", text='')

        row = col.row()
        row.prop(settings, "color_space")


@rpraddon.register_class
class RPRRender_PT_gamma_correction(RPRPanel, Panel):
    bl_label = "RPR Gamma Correction"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(context.scene.rpr.render.gamma_correction, "enable", text='')

    def draw(self, context):
        layout = self.layout
        settings = context.scene.rpr.render.gamma_correction
        col = layout.column()
        col.enabled = settings.enable
        row = col.row(align=True)
        row.prop(settings, "display_gamma")
        row = col.row(align=True)
        row.prop(settings, "viewport_only")


@rpraddon.register_class
class RPRRender_PT_depth_of_field(RPRPanel, Panel):
    bl_label = "RPR Depth of Field"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(context.scene.rpr.render.dof, "enable", text='')

    def draw(self, context):
        layout = self.layout
        camera = context.scene.camera

        scene_has_camera = len([obj for obj in context.scene.objects if obj.type == 'CAMERA']) > 0

        if camera:
            if camera.type == 'CAMERA':
                draw_camera_dof(context, layout, camera.data)
                layout.label('Active camera: ' + camera.name)
            else:
                layout.label("DoF supported by camera only.")
        else:
            if scene_has_camera:
                layout.label("Scene hasn't active camera.")
            else:
                layout.label("No camera found in scene.")


@rpraddon.register_class
class RPRRender_PT_motion_blur(RPRPanel, Panel):
    bl_label = "RPR Motion Blur"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(context.scene.rpr.render, "motion_blur", text='')

    def draw(self, context):
        layout = self.layout
        settings = context.scene.rpr.render
        col = layout.column()
        col.enabled = settings.motion_blur
        col1, col2, is_row = create_ui_autosize_column(context, col)
        col1.prop(settings, "motion_blur_exposure_apply", text="")
        col1.prop(settings, "motion_blur_exposure")
        col2.prop(settings, "motion_blur_scale_apply", text="")
        col2.prop(settings, "motion_blur_scale")


@rpraddon.register_class
class OpGpuList(bpy.types.Operator):
    bl_idname = "rpr.op_gpu_list"
    bl_label = "Select GPU"

    gpu_states = bpy.props.BoolVectorProperty(name="", size=helpers.RenderResourcesHelper.max_gpu_count)

    def draw(self, context):
        layout = self.layout
        settings = helpers.get_user_settings()

        for i, device in enumerate(helpers.render_resources_helper.devices):
            if i >= helpers.RenderResourcesHelper.max_gpu_count:
                break

            name = device['name']
            if not device['certified']:
                if not settings.include_uncertified_devices:
                    continue
                name += ' (not certified)'
            layout.prop(self, "gpu_states", index=i, text=name)

    def execute(self, context):
        global gpu_states
        helpers.render_resources_helper.update_gpu_states_in_settings(self.gpu_states)

        # update GPU value (clamp)
        max_count = helpers.render_resources_helper.get_max_gpu_can_use()
        settings = helpers.get_user_settings()
        if settings.gpu_count > max_count:
            settings.gpu_count = max_count
        return {'FINISHED'}

    def invoke(self, context, event):
        global gpu_states
        settings = helpers.get_user_settings()
        for i in range(len(self.gpu_states)):
            self.gpu_states[i] = settings.gpu_states[i]
        return context.window_manager.invoke_props_dialog(self)


@rpraddon.register_class
class RPRRender_PT_completion_criteria(RPRPanel, Panel):
    bl_label = "RPR Sampling"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def register(cls):
        cls.hours = bpy.props.IntProperty(
            name="hours",
            description="Limit iterations hours for production render",
            min=0, max=0x7fffffff, default=0,
        )

    def draw_header(self, context):
        pass

    def draw(self, context):
        layout = self.layout
        limits = context.scene.rpr.render.rendering_limits

        col = layout.column()
        col.enabled = limits.enable
        row = col.row()
        row.prop(limits, "type", expand=True)

        if 'TIME' == limits.type:
            row = col.row(align=True)
            row.alignment = 'EXPAND'
            row.prop(limits, "hours")
            row.prop(limits, "minutes")
            row.prop(limits, "seconds")
        elif 'ITER' == limits.type:
            row = col.row()
            row.prop(limits, "iterations")

        rpr_aa = context.scene.rpr.render.aa
        col1, col2, is_row = create_ui_autosize_column(context, layout)
        col1.label('Anti-Aliasing:')
        col1.prop(rpr_aa, "filter", text='')
        if is_row:
            col1.alignment = 'EXPAND'
            col1.prop(rpr_aa, "radius", slider=True, text='Radius')
        else:
            col2.label('')
            col2.prop(rpr_aa, "radius", slider=True, text='Radius')


@rpraddon.register_class
class RPRRender_PT_preview_settings(RPRPanel, Panel):
    bl_label = "RPR Material Preview Settings"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = bpy.context.scene.rpr.render_preview
        layout.prop(settings.rendering_limits, "iterations")
        layout.prop(settings.aa, "filter")



@rpraddon.register_class
class RPRRender_PT_environment(RPRPanel, Panel):
    bl_label = "RPR Environment IBLs and Sun & Sky"
    bl_context = "world"

    @classmethod
    def poll(cls, context):
        return context.scene.world and super().poll(context)

    def draw_maps(self, col, maps):
        col.prop(maps, "override_background")
        row = col.row()

        if maps.override_background:
            row.prop(maps, "override_background_type", expand=True)

            if maps.override_background_type == "image":
                if versions.is_blender_support_ibl_image():
                    col.template_ID(maps, "background_image", open="image.open")
                else:
                    col.prop(maps, "background_map", text='')
            else:
                row = col.row()
                row.prop(maps, "background_color")

    def draw_header(self, context):
        self.layout.prop(context.scene.world.rpr_data.environment, "enable", text="")

    def draw(self, context):
        layout = self.layout
        env = context.scene.world.rpr_data.environment
        col = layout.column()
        col.enabled = env.enable
        row = col.row()
        row.prop(env, "type", expand=True)

        if env.type == 'IBL':
            box = col.box()
            row = box.row()
            row.prop(env.ibl, 'type', expand=True)
            row = box.row()

            if env.ibl.type == 'COLOR':
                row.prop(env.ibl, "color")
            else:
                if versions.is_blender_support_ibl_image():
                    row.template_ID(env.ibl, "ibl_image", open="image.open")
                else:
                    row.prop(env.ibl, "ibl_map", text='')

            row = box.row()
            row.prop(env.ibl, "intensity")

            self.draw_maps(col, env.ibl.maps)

        elif env.type == 'SUN_SKY':
            box = col.box()
            col_base = box.column()
            col_base.label("Generic Sun & Sky parameters:")
            row1 = col_base.row()

            row = row1.column(align=True)
            row.alignment = 'EXPAND'
            row.prop(env.sun_sky, "turbidity")
            row.prop(env.sun_sky, "intensity")
            row.prop(env.sun_sky, "sun_glow")
            row.prop(env.sun_sky, "sun_disc")

            row = row1.column(align=True)
            row.alignment = 'EXPAND'
            row.prop(env.sun_sky, "saturation")
            row.prop(env.sun_sky, "horizon_height")
            row.prop(env.sun_sky, "horizon_blur")

            row = col_base.row()
            row1 = row.column()
            row1.prop(env.sun_sky, "filter_color")
            row1 = row.column()
            row1.prop(env.sun_sky, "ground_color")

            row = col_base.row()
            row.label('Texture resolution:')
            row = col_base.row()
            row.prop(env.sun_sky, "texture_resolution", expand=True)

            box = col.box()
            row = box.row()
            row.label("Sun & Sky System:")
            row = box.row()
            row.prop(env.sun_sky, "type", expand=True)
            if env.sun_sky.type == 'analytical_sky':
                row1 = box.row(align=True)
                row1.alignment = 'EXPAND'
                row1.prop(env.sun_sky, "azimuth")
                row1.prop(env.sun_sky, "altitude")
            elif env.sun_sky.type == 'date_time_location':
                row1 = box.row()
                row = row1.column(align=True)
                row.alignment = 'EXPAND'
                row.prop(env.sun_sky, "time_hours")
                row.prop(env.sun_sky, "time_minutes")
                row.prop(env.sun_sky, "time_seconds")

                row = row1.column(align=True)
                row.alignment = 'EXPAND'
                row.prop(env.sun_sky, "date_month")
                row.prop(env.sun_sky, "date_day")
                row.prop(env.sun_sky, "date_year")

                row = box.row()
                col1 = row.column()
                col1.prop(env.sun_sky, "time_zone")
                col1 = row.column()
                col1.operator('rpr.op_get_time_now', text='Now', icon='TIME')
                row = box.row()
                row.prop(env.sun_sky, "daylight_savings")

                box = col.box()
                row = box.row(align=True)
                row.label("Location")
                row1 = box.row(align=True)
                row1.alignment = 'EXPAND'
                row1.prop(env.sun_sky, "latitude")
                row1.prop(env.sun_sky, "longitude")

                row.alignment = 'EXPAND'
                row.operator("view3d.location_select", text="By Map", icon='WORLD')
                row.operator("rpr.location_select_by_city", text="By City", icon="SYNTAX_ON")

        box = col.box()
        col1, col2, is_row = create_ui_autosize_column(context, box)
        col1.label('Object:')
        row = col1.row(align=True)
        row.prop_search(env, 'gizmo', bpy.data, 'objects', text='')
        if not env.gizmo:
            row.operator("rpr.op_create_environment_gizmo", icon='ZOOMIN', text="").rotation = env.gizmo_rotation
        col2.prop(env, 'gizmo_rotation')

        layout.separator()
        layout.prop(get_render_passes_aov(context), "transparent", text="Transparent Background")


@rpraddon.register_class
class OpCreateEnvironmentGizmo(bpy.types.Operator):
    bl_idname = "rpr.op_create_environment_gizmo"
    bl_label = "Create Environment Gizmo"

    rotation = bpy.props.FloatVectorProperty(
        name='Rotation', description='Rotation',
        subtype='EULER', size=3
    )
    object_name = 'EnvObject'

    def execute(self, context):
        # verteces, edges = createRoseShape()
        # shape_scale = 0.03
        # me = bpy.data.meshes.new(self.object_name + 'Mesh')
        # me.from_pydata(verteces, edges, [])
        # me.update()
        # obj = bpy.data.objects.new(self.object_name, me)
        # bpy.context.scene.objects.link(obj)
        # obj.location = (0, 0, 0)
        # obj.scale = (shape_scale, shape_scale, shape_scale)
        # obj.rotation_euler = self.rotation
        # obj.draw_type = 'WIRE'
        # obj.hide_render = True
        # context.scene.world.rpr_data.environment.gizmo = obj.name

        obj = bpy.data.objects.new(self.object_name, None)
        obj.location = (0, 0, 0)
        obj.rotation_euler = self.rotation
        obj.empty_draw_size = 3.0
        obj.empty_draw_type = 'PLAIN_AXES'
        bpy.context.scene.objects.link(obj)
        context.scene.world.rpr_data.environment.gizmo = obj.name
        return {'FINISHED'}


@rpraddon.register_class
class OpGetTimeNow(bpy.types.Operator):
    bl_idname = "rpr.op_get_time_now"
    bl_label = "Get Time Now"

    @classmethod
    def poll(cls, context):
        return context.scene.world

    def execute(self, context):
        prop = context.scene.world.rpr_data.environment.sun_sky
        local = datetime.now()
        prop.date_year = local.year
        prop.date_month = local.month
        prop.date_day = local.day
        prop.time_hours = local.hour
        prop.time_minutes = local.minute
        prop.time_seconds = local.second
        context.scene.update_tag()
        return {'FINISHED'}


@rpraddon.register_class
class RPRRender_PT_quality_and_type(RPRPanel, Panel):
    bl_label = "RPR Mode/Quality"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        rpr = context.scene.rpr.render
        split = layout.split(percentage=0.45)
        row = split.column()
        row.label('Render Mode:')
        row.label('Viewport Quality:')

        row = split.column()
        row.prop(rpr, "render_mode", text='')
        row.prop(rpr, "viewport_quality", text='')

        layout.separator()
        rpr_gi = rpr.global_illumination

        row = layout.row()
        split = row.split(percentage=0.66)
        row1 = split.row()
        row1.enabled = rpr_gi.use_clamp_irradiance
        row1.prop(rpr_gi, "clamp_irradiance")

        row = layout.row()
        col = row.column(align=True)
        col.prop(rpr_gi, "max_ray_depth", slider=True)

        row = layout.row()
        col = row.column(align=True)
        col.prop(rpr_gi, "ray_epsilon", slider=True)

        row = split.column()

        row.prop(rpr_gi, "use_clamp_irradiance")

        layout.separator()

        self.layout.prop(rpr, "texturecompression")


@rpraddon.register_class
class RPRRender_PT_layers(RPRPanel, Panel):
    bl_label = "RPR Layers"
    bl_context = "render_layer"

    def draw(self, context):
        scene = context.scene

        split = self.layout.split()

        col = split.column()
        col.prop(scene, "layers", text="Scene")
        col.prop(scene.render.layers.active, "layers_exclude", text="Exclude")

        col = split.column()
        col.prop(scene.render.layers.active, "layers", text="Layer")

@rpraddon.register_class
class RPRRender_PT_passes_aov(RPRPanel, Panel):
    bl_label = "RPR Passes & AOVs"
    bl_context = "render_layer"

    if is_blender_support_aov():
        bl_context = "render_layer"
    else:
        bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.render.layers.active and super().poll(context)

    def draw_header(self, context):
        self.layout.prop(get_render_passes_aov(context), "enable", text="")

    def draw(self, context):
        layout = self.layout
        passes = get_render_passes_aov(context)
        col = layout.column()
        col.enabled = passes.enable
        row = col.row()

        if context.region.width > 200:
            row.prop(passes, 'pass_displayed')
            row = col.box()

            split = row.split(percentage=0.5)
            col1 = split.column()
            split = split.split()
            col2 = split.column(align=True)
        else:
            row.label('Pass Displayed:')
            row = col.row()
            row.prop(passes, 'pass_displayed', text='')

            row = col.box()
            col1 = row.column()
            col2 = col1


        count = math.ceil(len(passes.render_passes_items) * 0.5)
        for i, set in enumerate(passes.render_passes_items):
            col = col2 if i >= count else col1
            col.prop(passes, 'passesStates', index=i, text=set[1])

@rpraddon.register_class
class RPRRender_PT_Denoiser(RPRPanel, Panel):
    bl_label = "RPR Denoiser"
    bl_context = "render_layer"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(context.scene.rpr.render.denoiser, "enable", text='')

    def draw(self, context):
        layout = self.layout
        settings = context.scene.rpr.render.denoiser
        col = layout.column()
        col.enabled = settings.enable

        row = col.row()
        row.prop(settings, "filter_type")

        import pyrprimagefilters
        if settings.filter_type_values[settings.filter_type] == pyrprimagefilters.IMAGE_FILTER_BILATERAL_DENOISE:
            col.prop(settings, "radius")
            col.prop(settings, 'color_sigma', slider=True)
            col.prop(settings, 'normal_sigma', slider=True)
            col.prop(settings, 'p_sigma', slider=True)
            col.prop(settings, 'trans_sigma', slider=True)
        elif settings.filter_type_values[settings.filter_type] == pyrprimagefilters.IMAGE_FILTER_EAW_DENOISE:
            col.prop(settings, 'color_sigma', slider=True)
            col.prop(settings, 'normal_sigma', slider=True)
            col.prop(settings, 'depth_sigma', slider=True)
            col.prop(settings, 'trans_sigma', slider=True)
        elif settings.filter_type_values[settings.filter_type] == pyrprimagefilters.IMAGE_FILTER_LWR_DENOISE:
            col.prop(settings, 'samples', slider=True)
            col.prop(settings, 'half_window', slider=True)
            col.prop(settings, 'bandwidth', slider=True)
            


def draw_camera_settings(camera, layout):
    layout.prop(camera, "panorama_type")
    split = layout.split(percentage=0.33)
    row = split.column()
    row = split.column()
    row.prop(camera, "stereo")


@rpraddon.register_class
class RPRRender_PT_camera_settings(RPRPanel, Panel):
    bl_label = "RPR Camera Type"
    bl_options = {'DEFAULT_CLOSED'}
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.camera and super().poll(context)

    def draw_header(self, context):
        self.layout.prop(context.scene.rpr.render.camera, "override_camera_settings", text='')

    def draw(self, context):
        layout = self.layout
        rpr = context.scene.rpr
        col_base = layout.column()
        col_base.enabled = rpr.render.camera.override_camera_settings
        camera = rpr.render.camera
        draw_camera_settings(camera, col_base)


@rpraddon.register_class
class RPRRender_PT_settings(RPRPanel, Panel):
    bl_label = "RPR Stamp Settings"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(context.scene.rpr, "use_render_stamp", text='')

    def draw(self, context):
        layout = self.layout
        rpr = context.scene.rpr
        row = layout.column()
        row.enabled = rpr.use_render_stamp
        row.label("Render Stamp:")
        row.prop(rpr, "render_stamp", text="")

@rpraddon.register_class
class RPRRender_PT_developer(RPRPanel, Panel):
    bl_label = "RPR Developer Diagnostics"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        dev = context.scene.rpr.dev
        col = layout.column()
        col.prop(dev, "show_rpr_materials_with_errors")
        col.prop(dev, "show_cycles_materials_with_errors")
        col.prop(dev, "trace_dump")
        row = col.row()
        row.enabled = dev.trace_dump
        row.prop(dev, "trace_dump_folder", text="")
        path = dev.get_trace_dump_folder()
        row.operator("wm.path_open", text="", icon="RESTRICT_VIEW_OFF").filepath = path


@rpraddon.register_class
class OpExportRPRModel(Operator, ExportHelper):
    bl_idname = "rpr.export_model"
    bl_label = "Export RPR"
    filename_ext = ".rpr"

    filter_glob = bpy.props.StringProperty(
        default="*.rpr",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return export_rpr_model(context, self.filepath)


def export_rpr_model(context, filepath):
    from rprblender import sync, export
    import rprblender.render.scene
    scene = bpy.context.scene
    settings = scene.rpr.render

    render_device = rprblender.render.get_render_device(is_production=False)
    scene_synced = sync.SceneSynced(render_device, settings)

    render_resolution = (640, 480)

    render_camera = sync.RenderCamera()
    sync.extract_render_camera_from_blender_camera(scene.camera, render_camera, render_resolution, 1, settings, scene,
                                                   border=None)

    scene_synced.set_render_camera(render_camera)

    with rprblender.render.core_operations(raise_error=True):
        scene_synced.make_core_scene()

    try:
        scene_exporter = export.SceneExport(scene, scene_synced, ['MESH', 'CURVE'])
        scene_exporter.sync_environment_settings(scene.world.rpr_data.environment if scene.world else None)
        scene_exporter.export()

        logging.info("Exporting RPR model to:", filepath)
        result = pyrpr_load_store.export(filepath, render_device.core_context, scene_synced.get_core_scene())
        if result == 0:
            logging.info("Export complete")
        else:
            logging.info("Export failed - error:", result)
    except:
        logging.error("Export failed with an exception")
    finally:
        del scene_exporter
        scene_synced.destroy()
        del scene_synced

    return {'FINISHED'}

@rpraddon.register_class
class OpExportGLTFModel(Operator, ExportHelper):
    bl_idname = "rpr.export_gltf"
    bl_label = "Export GLTF"
    filename_ext = ".gltf"

    filter_glob = bpy.props.StringProperty(
        default="*.gltf",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return export_gltf_model(self.filepath)

def export_gltf_model(filepath):
    
    if platform.system() == "Darwin":  # TODO : GLTF
        logging.info("GLTF is not implemented on this platform.")
        return

    import pyrprgltf
    from rprblender import sync, export
    import rprblender.render.scene

    render_device = rprblender.render.get_render_device()
    context = render_device.core_context
    material_system = render_device.core_material_system
    uber_context = pyrprgltf.Object('rprx_context', render_device.core_uber_rprx_context)

    count = len(bpy.data.scenes)

    scene = bpy.context.scene
    settings = scene.rpr.render
    scene_synced = sync.SceneSynced(render_device, settings)

    render_resolution = (640, 480)

    render_camera = sync.RenderCamera()
    sync.extract_render_camera_from_blender_camera(scene.camera, render_camera, render_resolution, 1, settings, scene,
                                                   border=None)

    scene_synced.set_render_camera(render_camera)

    with rprblender.render.core_operations(raise_error=True):
        scene_synced.make_core_scene()
    try:
        scene_exporter = export.SceneExport(scene, scene_synced, ['MESH', 'CURVE'])
        scene_exporter.sync_environment_settings(scene.world.rpr_data.environment if scene.world else None)
        scene_exporter.export()
        rpr_scene = scene_synced.get_core_scene()

        rpr_scene_array = pyrprgltf.ArrayObject("rpr_scene[]", [rpr_scene._handle_ptr[0]])

        file_name = bytes(filepath, encoding="latin1")
        pyrprgltf.ExportToGLTF(file_name, context, material_system, uber_context, 
                           rpr_scene_array._handle_ptr, 1)
    except:
        logging.error("Export failed with an exception")
    finally:
        del scene_exporter
        scene_synced.destroy()
        del scene_synced

    return {'FINISHED'}


def add_rpr_export_menu_item(self, context):
    self.layout.operator(OpExportRPRModel.bl_idname, text="Radeon ProRender (.rpr)")
    self.layout.operator(OpExportGLTFModel.bl_idname, text="GLTF (.gltf)")


links = (('main_site', "Main Site",         "http://pro.radeon.com/en-us/software/prorender/"),
         ('documentation', "Documentation", "http://pro.radeon.com/en-us/software/prorender/"),
         ('downloads', "Downloads",         "http://pro.radeon.com/en-us/software/prorender/"),
         ('community', "Community",         "http://blender.radeonprorender.com/support/discussions"),
         ('knowledge_base', "Knowledge Base", "http://blender.radeonprorender.com/support/home"),
         ('bug_reports', "Bug Reports",     "http://blender.radeonprorender.com/support/login"),
        )


class AboutPanelHelper:
    instance = None

    def __init__(self):
        self.previews = bpy.utils.previews.new()
        self.preview = None

    def __del__(self):
        bpy.utils.previews.remove(self.previews)

    def get_image(self):
        if not self.preview:
            path_img = str((Path(rprblender.__file__).parent / 'img/rpr_logo.png').resolve())
            self.preview = self.previews.load("test", path_img, "IMAGE", False)
            self.preview.image_size[0]
        return [("Logo", "", '', self.preview.icon_id, 0)]


@rpraddon.register_class
class RPRLogoProperties(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.WindowManager.rpr_logo = bpy.props.PointerProperty(
            name="Radeon ProRender Logo",
            description="Radeon ProRender Logo",
            type=cls,
        )
        cls.logo = bpy.props.EnumProperty(
            name="Logo",
            items=cls.logo_load,
        )

    @classmethod
    def unregister(cls):
        del bpy.types.WindowManager.rpr_logo

    @staticmethod
    def logo_load(self, context):
        return AboutPanelHelper.instance.get_image()


@rpraddon.register_class
class RPRRender_PT_about(RPRPanel, Panel):
    bl_label = "RPR About"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        rpr = context.scene.rpr

        row = layout.row()
        row.scale_y = 1.95
        row.template_icon_view(context.window_manager.rpr_logo, "logo", False)

        box = layout.box()
        col = box.column()
        row = col.row(align=True)
        row.alignment = 'CENTER'

        info = versions.get_addon_info()
        ver = info['version'];
        row.label("%s for Blender v%d.%d.%d" % (info['name'], ver[0], ver[1], ver[2]))
        row = col.row(align=True)
        row.alignment = 'CENTER'
        row.label("© 2016 Advanced Micro Devices, Inc. (AMD)")
        row = col.row(align=True)
        row.alignment = 'CENTER'
        row.label("Portions of this software are created")
        row = col.row(align=True)
        row.alignment = 'CENTER'
        row.label("and copyrighted to other third parties.")

        row = layout.row(align=True)
        row.alignment = 'CENTER'
        self.add_link_button(row, "main_site")
        self.add_link_button(row, "documentation")
        self.add_link_button(row, "downloads")

        row = layout.row(align=True)
        row.alignment = 'CENTER'

        self.add_link_button(row, "community")
        self.add_link_button(row, "knowledge_base")
        self.add_link_button(row, "bug_reports")

        row = layout.row(align=True)
        row.alignment = 'CENTER'
        row.operator("rpr.op_show_eula")

    def add_link_button(self, row, page):
        caption = next(item[1] for item in links if page == item[0])
        row.operator("rpr.op_open_web_page", text=caption).page = page


@rpraddon.register_class
class OpOpenWebPage(bpy.types.Operator):
    bl_idname = "rpr.op_open_web_page"
    bl_label = "Open Web Page"

    page = bpy.props.EnumProperty(name="Page", items=links)

    def execute(self, context):
        url = next(item[2] for item in links if self.page == item[0])
        import webbrowser
        webbrowser.open(url)
        return {'FINISHED'}


@rpraddon.register_class
class OpOpenWebPage(bpy.types.Operator):
    bl_idname = "rpr.op_show_eula"
    bl_label = "EULA"

    def execute(self, context):
        path = str(Path(rprblender.__file__).parent / 'EULA.html')
        logging.info('EULA path: ', path)
        import webbrowser
        webbrowser.open(path)
        return {'FINISHED'}




########################################################################################################################
# Materials panel
########################################################################################################################

@rpraddon.register_class
class RPR_PT_context_material(RPRPanel, Panel):
    bl_label = ""
    bl_context = "material"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        return (context.material or context.object) and RPRPanel.poll(context)

    def draw(self, context):
        layout = self.layout
        mat = context.material
        ob = context.object
        slot = context.material_slot
        space = context.space_data

        if ob:
            is_sortable = len(ob.material_slots) > 1
            rows = 1
            if (is_sortable):
                rows = 4

            row = layout.row()
            row.template_list("MATERIAL_UL_matslots", "", ob, "material_slots", ob, "active_material_index", rows=rows)
            col = row.column(align=True)
            col.operator("object.material_slot_add", icon='ZOOMIN', text="")
            col.operator("object.material_slot_remove", icon='ZOOMOUT', text="")

            col.menu("MATERIAL_MT_specials", icon='DOWNARROW_HLT', text="")

            if is_sortable:
                col.separator()
                col.operator("object.material_slot_move", icon='TRIA_UP', text="").direction = 'UP'
                col.operator("object.material_slot_move", icon='TRIA_DOWN', text="").direction = 'DOWN'

            if ob.mode == 'EDIT':
                row = layout.row(align=True)
                row.operator("object.material_slot_assign", text="Assign")
                row.operator("object.material_slot_select", text="Select")
                row.operator("object.material_slot_deselect", text="Deselect")

        split = layout.split(percentage=0.65)

        if ob:
            split.template_ID(ob, "active_material", new="material.new")
            row = split.row()
            if slot:
                row.prop(slot, "link", text="")
            else:
                row.label()
        elif mat:
            split.template_ID(space, "pin_id")
            split.separator()

        node_tree_selector_draw(layout, mat, shader_node_output_name)
        if not panel_node_draw(layout, mat, shader_node_output_name, 'Shader'):
            row = self.layout.row(align=True)
            if slot is not None and slot.name:
                row.label("Material type")


def find_node_input(node, name):
    for input in node.inputs:
        if input.name == name:
            return input
    return None


def panel_node_draw(layout, id_data, output_type, input_name):
    node = find_node(id_data, output_type)
    if not node:
        return False
    else:
        tree = id_data.node_tree
        if tree:
            input = find_node_input(node, input_name)
            layout.template_node_view(tree, node, input)

    return True


def node_tree_selector_draw(layout, material, output_type):
    if material and not material.node_tree:
        layout.operator("rpr.op_material_add_nodetree", icon='NODETREE')
    layout.separator()


def activate_shader_editor():
    activate_editor('RPRTreeType')


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


@rpraddon.register_class
class RPRMaterial_PT_preview(RPRPanel, Panel):
    bl_label = "Preview"
    bl_context = "material"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.material and RPRPanel.poll(context)

    def draw(self, context):
        self.layout.template_preview(context.material)


def add_subdivision_properties(layout, object):
    if object:
        layout.prop(object.rpr_object, "subdivision")
        layout.prop(object.rpr_object, "subdivision_crease_weight", text='Crease Weight')
        layout.prop(object.rpr_object, "subdivision_boundary")


@rpraddon.register_class
class RPRObject_PT(RPRPanel, Panel):
    bl_label = "RPR Settings"
    bl_context = 'object'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.object and super().poll(context)

    def draw(self, context):
        if context.object.type in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META'):
            rpr = context.object.rpr_object
            self.layout.prop(rpr, "shadowcatcher")
            self.layout.prop(rpr, "shadows", text="Casts shadows")
            self.layout.prop(rpr, "portallight")

            visibility_layout = self.layout
            visibility_layout.prop(rpr, "visibility_in_primary_rays", text="Camera visibility:")

            subdivision_layout = self.layout.box()
            add_subdivision_properties(subdivision_layout, context.object)


@rpraddon.register_class
class RPRObject_PT_MotionBlur(RPRPanel, Panel):
    bl_label = "RPR Motion Blur"
    bl_context = 'object'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.object and (context.object.type in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META')) and \
            super().poll(context)

    def draw_header(self, context):
        row = self.layout.row()
        row.active = context.scene.rpr.render.motion_blur 
        row.prop(context.object.rpr_object, "motion_blur", text='')

    def draw(self, context):
        row = self.layout.row()
        row.active = context.scene.rpr.render.motion_blur
        row.enabled = context.object.rpr_object.motion_blur
        row.prop(context.object.rpr_object, "motion_blur_scale");


@rpraddon.register_class
class RPRCamra_PT(RPRPanel, Panel):
    bl_label = "RPR Settings"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.camera and super().poll(context) and 'PANO' == context.camera.type

    def draw(self, context):
        draw_camera_settings(context.camera.rpr_camera, self.layout)


@rpraddon.register_class
class OpAddMaterialNodeTree(bpy.types.Operator):
    bl_idname = "rpr.op_material_add_nodetree"
    bl_label = "Add Material NodeTree"

    def execute(self, context):
        context.material.use_nodes = True
        tree = context.material.node_tree
        tree.nodes.clear()
        shader = tree.nodes.new("rpr_shader_node_uber2")
        shader.location = 150, 400
        matOut = tree.nodes.new(shader_node_output_name)
        matOut.location = 550, 400
        tree.links.new(shader.outputs[0], matOut.inputs[0])
        activate_shader_editor()
        return {'FINISHED'}


def draw_camera_dof(context, layout, camera):
    dof_options = camera.gpu_dof

    row = layout.row()

    col1, col2, is_row = create_ui_autosize_column(context, layout)
    col1.enabled = context.scene.rpr.render.dof.enable
    col2.enabled = context.scene.rpr.render.dof.enable

    col1.label("Focus:")
    col1.prop(camera, "dof_object", text="")
    sub = col1.row()
    sub.active = camera.dof_object is None
    sub.prop(camera, "dof_distance", text="Distance")

    col2.label("Params:")
    col2.prop(dof_options, "fstop")
    col2.prop(dof_options, "blades")


@rpraddon.register_class
class RPRCamera_PT_dof(RPRPanel, Panel):
    bl_label = "RPR Depth of Field"
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return context.camera and RPRPanel.poll(context)

    def draw_header(self, context):
        self.layout.prop(context.scene.rpr.render.dof, "enable", text='')

    def draw(self, context):
        layout = self.layout
        cam = context.camera
        draw_camera_dof(context, layout, cam)


@rpraddon.register_class
class RPRCamera_PT_motion_blur(RPRPanel, Panel):
    bl_label = "RPR Motion Blur"
    bl_options = {'DEFAULT_CLOSED'}
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return context.camera and RPRPanel.poll(context)

    def draw_header(self, context):
        row = self.layout.row()
        row.active = context.scene.rpr.render.motion_blur
        row.prop(context.camera.rpr_camera, "motion_blur", text='')

    def draw(self, context):
        row = self.layout.row()
        row.active = context.scene.rpr.render.motion_blur
        row.enabled = context.camera.rpr_camera.motion_blur
        row.prop(context.camera.rpr_camera, "motion_blur_exposure")


@rpraddon.register_class
class RPRImage_PT_Tools(RPRPanel, bpy.types.Panel):
    bl_label = "RPR Tools"
    bl_context = "material"
    bl_options = {'DEFAULT_CLOSED'}
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == 'RPR'

    def draw(self, context):
        self.layout.operator('rpr.refresh_image')
        self.layout.operator('rpr.image_cache_purge')


########################################################################################################################
# Others
########################################################################################################################

def get_panels():
    # follow the Cycles model of excluding panels we don't want

    exclude_panels = {
        'DATA_PT_area',
        'DATA_PT_camera_dof',
        'DATA_PT_falloff_curve',
        'DATA_PT_lamp',
        'DATA_PT_preview',
        'DATA_PT_shadow',
        'DATA_PT_spot',
        'DATA_PT_sunsky',
        'MATERIAL_PT_context_material',
        'MATERIAL_PT_diffuse',
        'MATERIAL_PT_flare',
        'MATERIAL_PT_halo',
        'MATERIAL_PT_mirror',
        'MATERIAL_PT_options',
        'MATERIAL_PT_pipeline',
        'MATERIAL_PT_preview',
        'MATERIAL_PT_shading',
        'MATERIAL_PT_shadow',
        'MATERIAL_PT_specular',
        'MATERIAL_PT_sss',
        'MATERIAL_PT_strand',
        'MATERIAL_PT_transp',
        'MATERIAL_PT_volume_density',
        'MATERIAL_PT_volume_integration',
        'MATERIAL_PT_volume_lighting',
        'MATERIAL_PT_volume_options',
        'MATERIAL_PT_volume_shading',
        'MATERIAL_PT_volume_transp',
        'RENDERLAYER_PT_layer_options',
        'RENDERLAYER_PT_layer_passes',
        'RENDERLAYER_PT_views',
        'RENDER_PT_antialiasing',
        'RENDER_PT_bake',
        'RENDER_PT_motion_blur',
        'RENDER_PT_performance',
        'RENDER_PT_freestyle',
        'RENDER_PT_post_processing',
        'RENDER_PT_shading',
        'RENDER_PT_stamp',
        'SCENE_PT_simplify',
        'SCENE_PT_audio',
        'WORLD_PT_ambient_occlusion',
        'WORLD_PT_environment_lighting',
        'WORLD_PT_gather',
        'WORLD_PT_indirect_lighting',
        'WORLD_PT_mist',
        'WORLD_PT_preview',
        'WORLD_PT_world',
    }

    panels = []
    for t in bpy.types.Panel.__subclasses__():
        if hasattr(t, 'COMPAT_ENGINES') and 'BLENDER_RENDER' in t.COMPAT_ENGINES:
            if t.__name__ not in exclude_panels:
                panels.append(t)

    return panels


def register():
    logging.info("ui.register()")
    AboutPanelHelper.instance = AboutPanelHelper()

    bpy.types.RENDER_PT_render.append(draw_settings)
    bpy.types.DATA_PT_context_lamp.append(draw_lamp_settings)

    bpy.types.INFO_MT_file_export.append(add_rpr_export_menu_item)

    for panel in get_panels():
        panel.COMPAT_ENGINES.add('RPR')


def unregister():
    logging.info("ui.unregister()")
    del AboutPanelHelper.instance

    bpy.types.DATA_PT_context_lamp.remove(draw_lamp_settings)
    bpy.types.RENDER_PT_render.remove(draw_settings)

    bpy.types.INFO_MT_file_export.remove(add_rpr_export_menu_item)

    for panel in get_panels():
        panel.COMPAT_ENGINES.remove('RPR')
