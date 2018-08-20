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
from rprblender.images import get_automatic_compression_size

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


def draw_lamp_settings(self, context):
    if context.scene.render.engine != 'RPR':
        return

    lamp = context.lamp  # type: bpy.types.Lamp

    def draw_light_prop(layout):
        if lamp.type == 'AREA':
            col1, col2, is_row = create_ui_autosize_column(context, layout, True)
            col1.prop(lamp.rpr_lamp, 'shape', text="")

            if lamp.rpr_lamp.shape == 'RECTANGLE':
                col1.prop(lamp.rpr_lamp, 'size_1', text="Width")
                col1.prop(lamp.rpr_lamp, 'size_2', text="Height")
            elif lamp.rpr_lamp.shape == 'MESH':
                col1.prop_search(lamp.rpr_lamp, 'mesh_obj', context.scene, 'objects', 
                                 text="", icon='MESH_DATA')
            elif lamp.rpr_lamp.shape == 'CYLINDER':
                col1.prop(lamp.rpr_lamp, 'size_1', text="Radius")
                col1.prop(lamp.rpr_lamp, 'size_2', text="Length")
            else: # 'DISC', 'SPHERE'
                col1.prop(lamp.rpr_lamp, 'size_1', text="Radius")

            col2.prop(lamp.rpr_lamp, 'visible')
            row = col2.row()
            row.enabled = lamp.rpr_lamp.visible
            row.prop(lamp.rpr_lamp, 'cast_shadows')

        elif lamp.type == 'SPOT':
            col1, col2, is_row = create_ui_autosize_column(context, layout, True)
            col1.prop(lamp, 'spot_size', text="Angle", slider=True)
            col1.prop(lamp, 'spot_blend', text="Falloff", slider=True)

        elif lamp.type == 'SUN':
            layout.prop(lamp.rpr_lamp, 'shadow_softness')

        elif lamp.type == 'HEMI':
            layout.label("Hemi lamp is not supported by RPR.\nPlease use Sun lamp as directional light.")


    def draw_intensity(layout):
        if lamp.type in ('POINT', 'SPOT'):
            intensity_units = 'intensity_units_point'
        elif lamp.type == 'SUN':
            intensity_units = 'intensity_units_dir'
        else:
            intensity_units = 'intensity_units_area'

        col1, col2, is_row = create_ui_autosize_column(context, layout, True)
        col1.prop(lamp.rpr_lamp, intensity_units, text="")

        col1.prop(lamp.rpr_lamp, 'intensity')
        if getattr(lamp.rpr_lamp, intensity_units) in ('WATTS', 'RADIANCE'):
            col1.prop(lamp.rpr_lamp, 'luminous_efficacy', slider=True)
        elif lamp.type == 'AREA' and getattr(lamp.rpr_lamp, intensity_units) == 'DEFAULT':
            col1.prop(lamp.rpr_lamp, 'intensity_normalization')

        col2.row().prop(lamp.rpr_lamp, 'color')

        col2.prop(lamp.rpr_lamp, 'use_temperature', text = "Temperature")
        row = col2.row()
        row.enabled = lamp.rpr_lamp.use_temperature
        row.prop(lamp.rpr_lamp, 'temperature', text = "", slider=True)
        
        if lamp.type == 'AREA':
            col = layout.column()
            col.label("Light Color Map:")
            col.enabled = lamp.rpr_lamp.shape in ('RECTANGLE', 'DISC', 'MESH')
            if versions.is_blender_support_custom_datablock():
                col.template_ID(lamp.rpr_lamp, 'color_map', open='image.open')
            else:
                col.prop(lamp.rpr_lamp, 'color_map', text='')

        elif lamp.type == 'POINT':
            col = layout.column(align=True)
            col.label('IES Data File:')

            row = col.row(align=True)
            row.alignment = 'EXPAND'
            row.prop(lamp.rpr_lamp, "ies_file_name", text='')
            row.operator('rpr.op_select_ies_light_data', text='', icon='FILESEL')


    self.layout.row(align=True).prop(lamp, 'type', expand=True)

    draw_light_prop(self.layout)
    if lamp.type != 'HEMI':
        draw_intensity(self.layout.box())


from . import helpers


@rpraddon.register_class
class RPRRender_PT_render_resources(RPRPanel, Panel):
    bl_label = "RPR Final Render Device"

    def draw(self, context):
        layout = self.layout
        device_settings = helpers.get_device_settings(True)
        
        row = layout.split(percentage=0.25, align=True)
        col = row.column()
        col.prop(device_settings, 'use_cpu', text='CPU')
        col = row.column()
        box = col.box()
        box.enabled = device_settings.use_cpu
        box.prop(device_settings, 'cpu_threads')

        row = layout.split(percentage=0.25, align=True)
        col = row.column()
        col.prop(device_settings, 'use_gpu', text='GPU')
        col = row.column()
        box = col.box()
        box.enabled = device_settings.use_gpu
        for i, device_item in enumerate(helpers.render_resources_helper.devices):
            name = device_item['name']
            if not device_item['certified']:
                if not device_settings.include_uncertified_devices:
                    continue
                name += ' (not certified)'
            box.prop(device_settings, "gpu_states", index=i, text=name)

        layout.separator()

        row = layout.row()
        row.prop(device_settings, 'samples')

        # layout.separator()
        # row = layout.row()
        # row = layout.split(percentage=0.25, align=True)
        # col = row.column()
        # col.prop(final_settings, 'tiled_render')
        # col = row.column(align=True)
        # col.prop(final_settings, 'tile_x')
        # col.prop(final_settings, 'tile_y')


@rpraddon.register_class
class RPRRender_PT_viewport_settings(RPRPanel, Panel):
    bl_label = "RPR Preview Device and Settings"

    def draw(self, context):
        layout = self.layout

        device_settings = helpers.get_device_settings(False)
        
        row = layout.split(percentage=0.25, align=True)
        col = row.column()
        col.prop(device_settings, 'use_cpu', text='CPU')
        col = row.column()
        box = col.box()
        box.enabled = device_settings.use_cpu
        box.prop(device_settings, 'cpu_threads')

        row = layout.split(percentage=0.25, align=True)
        col = row.column()
        col.prop(device_settings, 'use_gpu', text='GPU')
        col = row.column()
        box = col.box()
        box.enabled = device_settings.use_gpu
        for i, device_item in enumerate(helpers.render_resources_helper.devices):
            name = device_item['name']
            if not device_item['certified']:
                if not device_settings.include_uncertified_devices:
                    continue
                name += ' (not certified)'
            box.prop(device_settings, "gpu_states", index=i, text=name)

        # settings for viewport overrides
        layout.separator()
        layout.label("Viewport Settings:")
        viewport_settings = helpers.get_user_settings().viewport_render_settings

        layout.prop(viewport_settings, 'limit_resolution', text="Resolution Limit")
        if viewport_settings.limit_resolution == 'SCALE':
            layout.prop(viewport_settings, 'resolution_scale', slider=True)

        layout.prop(viewport_settings.limits, "type", text="Iterations Limit")

        if 'TIME' == viewport_settings.limits.type:
            layout.prop(viewport_settings.limits, "seconds")
        elif 'ITER' == viewport_settings.limits.type:
            layout.prop(viewport_settings.limits, "iterations")

        layout.separator()
        row = layout.row()
        row.prop(viewport_settings, 'render_mode', text="Render Mode")

        row = layout.split()
        col = row.column(align=True)
        col.prop(viewport_settings, 'motion_blur', text='Show Motion Blur')
        col.prop(viewport_settings, 'dof', text='Show Depth of Field')

        col = row.column(align=True)
        col.prop(viewport_settings.gi_settings, 'max_ray_depth')
        col.prop(viewport_settings.gi_settings, 'max_diffuse_depth', text='Diffuse depth')
        col.prop(viewport_settings.gi_settings, 'max_glossy_depth', text='Reflection depth')

        layout.separator()
        row = layout.row()
        if viewport_settings.downscale_textures_size == 'AUTO':
            text = "Downscale Textures [%d]:" % get_automatic_compression_size(context.scene)
        else:
            text = "Downscale Textures:"
        row.prop(viewport_settings, 'downscale_textures_size', text=text)

        layout.separator()
        layout.prop(viewport_settings, 'thumbnail_iterations')
        

@rpraddon.register_class
class RPRRender_PT_completion_criteria(RPRPanel, Panel):
    bl_label = "RPR Render Sampling"
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
class RPRRender_PT_quality_and_type(RPRPanel, Panel):
    bl_label = "RPR Render Quality"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        rpr = context.scene.rpr.render

        layout.label("Ray Depths:")
        split = layout.split(percentage=0.5)
        col = split.column()
        rpr_gi = rpr.global_illumination

        col.prop(rpr_gi, "max_ray_depth", slider=True)

        col = split.column(align=True)
        col.prop(rpr_gi, "max_diffuse_depth", slider=True, text='Max Diffuse')
        col.prop(rpr_gi, "max_glossy_depth", slider=True, text='Max Glossy')
        col.prop(rpr_gi, "max_refraction_depth", slider=True, text='Max Refraction')
        col.prop(rpr_gi, "max_glossy_refraction_depth", slider=True, text='Max Glossy Refraction')
        col.prop(rpr_gi, "max_shadow_depth", slider=True, text='Max Shadow')

        layout.separator()
        row = layout.row()
        row.prop(rpr_gi, "ray_epsilon", slider=True)

        row = layout.row()
        split = row.split(percentage=0.25)
        row2 = split.row()
        row2.prop(rpr_gi, "use_clamp_irradiance")
        row1 = split.row()
        row1.enabled = rpr_gi.use_clamp_irradiance
        row1.prop(rpr_gi, "clamp_irradiance")
        
        layout.prop(rpr, 'downscale_textures_production')


@rpraddon.register_class
class RPRRender_PT_render_effects(RPRPanel, Panel):
    bl_label = "RPR Render Effects"

    def draw(self, context):
        layout = self.layout
        rpr = context.scene.rpr

        layout.prop(rpr.render.dof, "enable", text='Depth of Field')
        box = layout.box()
        box.enabled = rpr.render.dof.enable
        camera = context.scene.camera
        if camera and camera.type == 'CAMERA':
            box.label('Active camera: ' + camera.name)
            draw_camera_dof(context, box, camera.data)
        else:
            sub_row.label("Scene hasn't active camera.")

        layout.separator()
        layout.prop(rpr.render, "motion_blur", text='Motion Blur')
        box = layout.box()
        box.enabled = rpr.render.motion_blur

        split = box.split()
        col1 = split.column()
        col1.prop(rpr.render, "motion_blur_exposure_apply", text="")
        col1.prop(rpr.render, "motion_blur_exposure")
        col2 = split.column()
        col2.prop(rpr.render, "motion_blur_scale_apply", text="")
        col2.prop(rpr.render, "motion_blur_scale")

        if platform.system() != "Darwin":
            layout.separator()
            layout.prop(rpr, "use_render_stamp", text='Render Stamp')
            
            box = layout.box()
            box.enabled = rpr.use_render_stamp
            box.prop(rpr, "render_stamp", text="")

# @rpraddon.register_class
class RPRRender_PT_preview_settings(RPRPanel, Panel):
    bl_label = "RPR Material Preview Settings"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = bpy.context.scene.rpr.render_preview
        
        layout.prop(settings.rendering_limits, "iterations")
        



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
            col1 = split.column(align=True)
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

        if settings.filter_type == 'bilateral':
            col.prop(settings, "radius")
            col.prop(settings, 'color_sigma', slider=True)
            col.prop(settings, 'normal_sigma', slider=True)
            col.prop(settings, 'p_sigma', slider=True)
            col.prop(settings, 'trans_sigma', slider=True)
        elif settings.filter_type == 'eaw':
            col.prop(settings, 'color_sigma', slider=True)
            col.prop(settings, 'normal_sigma', slider=True)
            col.prop(settings, 'depth_sigma', slider=True)
            col.prop(settings, 'trans_sigma', slider=True)
        elif settings.filter_type == 'lwr':
            col.prop(settings, 'samples', slider=True)
            col.prop(settings, 'half_window', slider=True)
            col.prop(settings, 'bandwidth', slider=True)
        
        row = col.row()
        row.prop(settings, "enable_viewport")
        #row.prop(settings, "scale_by_iterations")


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


# @rpraddon.register_class
# class RPRRender_PT_settings(RPRPanel, Panel):
#     bl_label = "RPR Stamp Settings"
#     bl_options = {'DEFAULT_CLOSED'}

#     def draw_header(self, context):
#         layout = self.layout
#         row = layout.column()
#         row.enabled = False if platform.system() == "Darwin" else True
#         row.prop(context.scene.rpr, "use_render_stamp", text='')

#     def draw(self, context):
#         layout = self.layout
#         rpr = context.scene.rpr
#         row = layout.column()
#         row.enabled = False if platform.system() == "Darwin" else rpr.use_render_stamp
#         row.label("Render Stamp:")
#         row.prop(rpr, "render_stamp", text="")



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

    render_device = rprblender.render.get_render_device()
    scene_synced = sync.SceneSynced(render_device, settings)
    export.prev_world_matrices_cache.update(scene)

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
        scene_synced.destroy()
        export.prev_world_matrices_cache.purge()

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
    export.prev_world_matrices_cache.update(scene)

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

        for key, core_shape in scene_synced.objects_synced.items():
            if not type(key) is tuple:
                continue

            blender_obj = scene_exporter.objects_sync.object_instances[key[0]].blender_obj
            group_name = ("Group_" + blender_obj.parent.name) if blender_obj.parent else "Root"
            pyrprgltf.GLTF_AssignShapeToGroup(core_shape.core_obj, group_name.encode('latin1'))

            if blender_obj.parent:
                parent_group_name = ("Group_" + blender_obj.parent.parent.name) if blender_obj.parent.parent else "Root"
                pyrprgltf.GLTF_AssignParentGroupToGroup(group_name.encode('latin1'), parent_group_name.encode('latin1'))


        rpr_scene_array = pyrprgltf.ArrayObject("rpr_scene[]", [rpr_scene._handle_ptr[0]])
        pyrprgltf.ExportToGLTF(filepath.encode('latin1'), context, material_system, uber_context, 
                               rpr_scene_array._handle_ptr, 1)
    finally:
        scene_synced.destroy()
        export.prev_world_matrices_cache.purge()

    return {'FINISHED'}


def add_rpr_export_menu_item(self, context):
    self.layout.operator(OpExportRPRModel.bl_idname, text="Radeon ProRender (.rpr)")
    self.layout.operator(OpExportGLTFModel.bl_idname, text="GLTF (.gltf)")


links = (('main_site', "Main Site",         "https://pro.radeon.com/en/software/prorender/"),
         ('documentation', "Documentation", "https://pro.radeon.com/en/software/prorender/"),
         ('downloads', "Downloads",         "https://pro.radeon.com/en/software/prorender/blender/"),
         ('community', "Community",         "https://community.amd.com/community/prorender/"),
         ('bug_reports', "Bug Reports",     "https://community.amd.com/community/prorender/blender/"),
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
    bl_label = "RPR Help/About"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        def core_ver_str():
            core_ver = versions.get_core_version()
            mj = (core_ver & 0xFFFF00000) >> 28
            mn = (core_ver & 0xFFFFF) >> 8
            return "%x.%x" % (mj, mn)

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
        row.label("%s for Blender %d.%d.%d (core %s)" % (info['name'], ver[0], ver[1], ver[2], core_ver_str()))
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
        self.add_link_button(row, "bug_reports")

        row = layout.row(align=True)
        row.alignment = 'CENTER'
        row.operator("rpr.op_show_eula")

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
        layout.prop(object.rpr_object, "subdivision_type")
        if object.rpr_object.subdivision_type == 'level':
            layout.prop(object.rpr_object, "subdivision")
        else:
            layout.prop(object.rpr_object, "adaptive_subdivision")
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
            self.layout.prop(rpr, "reflection_visibility")
            self.layout.prop(rpr, "portallight")

            visibility_layout = self.layout
            visibility_layout.prop(rpr, "visibility_in_primary_rays", text="Camera visibility:")

            add_subdivision_properties(self.layout.box(), context.object)

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
        shader = tree.nodes.new("rpr_shader_node_uber3")
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

    bpy.types.DATA_PT_context_lamp.append(draw_lamp_settings)

    bpy.types.INFO_MT_file_export.append(add_rpr_export_menu_item)

    for panel in get_panels():
        panel.COMPAT_ENGINES.add('RPR')


def unregister():
    logging.info("ui.unregister()")
    del AboutPanelHelper.instance

    bpy.types.DATA_PT_context_lamp.remove(draw_lamp_settings)

    bpy.types.INFO_MT_file_export.remove(add_rpr_export_menu_item)

    for panel in get_panels():
        panel.COMPAT_ENGINES.remove('RPR')
