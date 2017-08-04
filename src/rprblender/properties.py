#!python3
import bpy
import os
import math
import ctypes
from . import rpraddon
import pyrpr
from . import logging
from pyrpr import ffi
from pathlib import Path
import rprblender
from rprblender.helpers import create_core_enum_for_property
from rprblender.environment_op import callback_draw_sun
import rprblender.render.render_layers
from . import versions

def convert_K_to_RGB(colour_temperature):
    # range check
    if colour_temperature < 1000:
        colour_temperature = 1000
    elif colour_temperature > 40000:
        colour_temperature = 40000

    tmp_internal = colour_temperature / 100.0
    # red
    if tmp_internal <= 66:
        red = 255
    else:
        tmp_red = 329.698727446 * math.pow(tmp_internal - 60, -0.1332047592)
        if tmp_red < 0:
            red = 0
        elif tmp_red > 255:
            red = 255
        else:
            red = tmp_red

    # green
    if tmp_internal <= 66:
        tmp_green = 99.4708025861 * math.log(tmp_internal) - 161.1195681661
        if tmp_green < 0:
            green = 0
        elif tmp_green > 255:
            green = 255
        else:
            green = tmp_green
    else:
        tmp_green = 288.1221695283 * math.pow(tmp_internal - 60, -0.0755148492)
        if tmp_green < 0:
            green = 0
        elif tmp_green > 255:
            green = 255
        else:
            green = tmp_green

    # blue
    if tmp_internal >= 66:
        blue = 255
    elif tmp_internal <= 19:
        blue = 0
    else:
        tmp_blue = 138.5177312231 * math.log(tmp_internal - 10) - 305.0447927307
        if tmp_blue < 0:
            blue = 0
        elif tmp_blue > 255:
            blue = 255
        else:
            blue = tmp_blue

    return red / 255.0, green / 255.0, blue / 255.0


def create_core_enum_property(cls, prefix, name, description, text_suffix="", default=None):
    prop_items, prop_default, prop_remap = create_core_enum_for_property(prefix, text_suffix)
    if default is not None:
        assert default in [v[0] for v in prop_items], prop_items
        prop_default = default

    prop = bpy.props.EnumProperty(
        name=name,
        items=prop_items,
        description=description,
        default=prop_default,
    )
    return prop, prop_remap


########################################################################################################################
# Passes AOV
########################################################################################################################
def states_change(self, context):
    if rprblender.render.render_layers.use_custom_passes:
        # 2.79 uses new api for render passes, where RenderEngine implements `update_render_passes`
        # method where it should register all passes used. That's enough to have those passes in the
        # compositor node and in the render result
        # see https://wiki.blender.org/index.php/Dev:Ref/Release_Notes/2.79/Add-ons
        update_render_passes(context)
        return

    # TODO: remove this when 2.78 is deprecated
    logging.warn("Using old Blender", bpy.app.version_string, "?")
    for i in range(len(self.render_passes_items)):
        name = self.render_passes_items[i][0]
        context.scene.render.layers.active.use_pass_combined = True
        context.scene.render.layers.active.use_pass_color = False

        if name == 'default':
            context.scene.render.layers.active.use_pass_combined = self.passesStates[i]
        if name == 'world_coordinate':
            context.scene.render.layers.active.use_pass_vector = self.passesStates[i]
        if name == 'uv':
            context.scene.render.layers.active.use_pass_uv = self.passesStates[i]
        if name == 'material_idx':
            context.scene.render.layers.active.use_pass_material_index = self.passesStates[i]
        if name == 'geometric_normal':
            context.scene.render.layers.active.use_pass_emit = self.passesStates[i]
        if name == 'shading_normal':
            context.scene.render.layers.active.use_pass_normal = self.passesStates[i]
        if name == 'depth':
            context.scene.render.layers.active.use_pass_z = self.passesStates[i]
        if name == 'object_id':
            context.scene.render.layers.active.use_pass_object_index = self.passesStates[i]


def update_render_passes(context):
    scene = context.scene
    rd = scene.render
    rl = rd.layers.active
    rl.update_render_passes()


def aov_enable_change(self, context):
    if rprblender.render.render_layers.use_custom_passes:
        update_render_passes(context)
    else:
        layer = context.scene.render.layers.active
        layer.use_pass_color = False
        layer.use_pass_vector = False
        layer.use_pass_uv = False
        layer.use_pass_material_index = False
        layer.use_pass_emit = False
        layer.use_pass_normal = False
        layer.use_pass_z = False
        layer.use_pass_object_index = False

        if self.enable:
            states_change(self, context)


@rpraddon.register_class
class RenderPassesAov(bpy.types.PropertyGroup):
    render_passes_items = (('default', "Color (default)", "Color (default) (layer 'Combined')"),
                           ('depth', "Depth", "Depth (layer 'Z')"),
                           ('uv', "UV", "UV (layer 'UV')"),
                           ('world_coordinate', "World Coordinate", "World Coordinate (layer 'Vector')"),
                           ('geometric_normal', "Geometric Normal", "Geometric Normal (layer 'Emit')"),
                           ('shading_normal', "Shading Normal", "Shading Normal (layer 'Normal')"),
                           ('object_id', "Object Id", "Object Id (layer 'IndexOB')"),
                           ('material_idx', "Material Index", "Material Index (layer 'IndexMA')"),
                           )

    enable = bpy.props.BoolProperty(
        name="Render Passes (AOV)",
        description="Render Layers / Passes & AOVs",
        default=versions.is_blender_support_aov(),
        update=aov_enable_change,
    )
    pass_displayed = bpy.props.EnumProperty(
        name='Pass Displayed',
        items=render_passes_items,
        description='Displayed In Render View',
        default='default',
    )
    passesStates = bpy.props.BoolVectorProperty(
        name="passesStates",
        description="Passes states",
        size=len(render_passes_items),
        update=states_change,
    )

    transparent = bpy.props.BoolProperty(
        name="Transparent",
        description="World background is transparent with premultiplied alpha",
        default=False
    )


########################################################################################################################
# Environment
########################################################################################################################

@rpraddon.register_class
class RenderEnvironmentMaps(bpy.types.PropertyGroup):
    override_background = bpy.props.BoolProperty(
        name="Override Background", description="Override the IBL background",
        default=False,
    )
    override_background_type = bpy.props.EnumProperty(
        name="Override Type",
        items=(("image", "Image", "Override the background with an image"),
               ("color", "Color", "Override the background with a color")),
        description="Background override type",
        default='image',
    )
    if versions.is_blender_support_ibl_image():
        background_image = bpy.props.PointerProperty(type=bpy.types.Image)
    else:
        background_map = bpy.props.StringProperty(
            name='Background Map', description='Background Map', subtype='FILE_PATH'
        )
    background_color = bpy.props.FloatVectorProperty(
        name='Background Color', description="The background override color",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    override_reflection_map = bpy.props.BoolProperty(
        name="Override Reflection Map", description="Override Reflection Map",
        default=False,
    )
    reflection_map = bpy.props.StringProperty(
        name='Reflection Map', description='Reflection Map', subtype='FILE_PATH'
    )
    override_refraction_map = bpy.props.BoolProperty(
        name="Override Refraction Map", description="Override Refraction Map",
        default=False,
    )
    refraction_map = bpy.props.StringProperty(
        name='Refraction Map', description='Refraction Map', subtype='FILE_PATH'
    )


@rpraddon.register_class
class RenderEnvironmentIBL(bpy.types.PropertyGroup):
    color = bpy.props.FloatVectorProperty(
        name='Default Color', description="Default Color to use when no IBL map set",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    intensity = bpy.props.FloatProperty(
        name="Intensity",
        description="Intensity",
        min=0.0, default=1.0,
    )
    use_ibl_map = bpy.props.BoolProperty(
        name="Use Image-Base Lighting Map", description="Use Image-Base Lighting Map",
        default=False,
    )

    if versions.is_blender_support_ibl_image():
        ibl_image = bpy.props.PointerProperty(type=bpy.types.Image)
    else:
        ibl_map = bpy.props.StringProperty(
            name='Image-Base Lighting Map', description='Image-Base Lighting Map', subtype='FILE_PATH'
        )

    maps = bpy.props.PointerProperty(type=RenderEnvironmentMaps)  # type: RenderEnvironmentMaps


@rpraddon.register_class
class RenderEnvironmentSunSky(bpy.types.PropertyGroup):
    def update_type(self, context):
        bpy.context.scene.world.rpr_data.environment.switch_sun_helper()

    type = bpy.props.EnumProperty(
        name="Sun & Sky System",
        items=(('analytical_sky', "Analytical Sky", "Analytical Sky"),
               ('date_time_location', "Date, Time and Location", "Date, Time and Location")),
        description="Sun & Sky System",
        default='analytical_sky',
        update=update_type
    )
    # Analytical Sky
    azimuth = bpy.props.FloatProperty(
        name="Azimuth",
        description="Azimuth",
        subtype='ANGLE',
        min=0, max=math.radians(360),
        default=0.0,
    )
    altitude = bpy.props.FloatProperty(
        name="Altitude",
        description="Altitude",
        subtype='ANGLE',
        min=math.radians(-90), max=math.radians(90),
        default=math.radians(30),
    )

    # Date, Time & Location
    latitude = bpy.props.FloatProperty(
        name="Latitude",
        description="Latitude",
        subtype='ANGLE',
        min=math.radians(-90), max=math.radians(90),
        default=math.radians(38),
    )
    longitude = bpy.props.FloatProperty(
        name="Longitude",
        description="Longitude",
        subtype='ANGLE',
        min=math.radians(-180), max=math.radians(180),
        default=math.radians(27),
    )

    date_year = bpy.props.IntProperty(
        name="Year",
        description="Year",
        # subtype='TIME',
        min=0, default=2016,
    )
    date_month = bpy.props.IntProperty(
        name="Month",
        description="Month",
        # subtype='TIME',
        min=1, max=12, default=1,
    )
    date_day = bpy.props.IntProperty(
        name="Day",
        description="Day",
        # subtype='TIME',
        min=1, max=31, default=1,
    )
    time_hours = bpy.props.IntProperty(
        name="Hours",
        description="Hours",
        subtype='TIME',
        min=0, max=23, default=12,
    )
    time_minutes = bpy.props.IntProperty(
        name="Minutes",
        description="Minutes",
        subtype='TIME',
        min=0, max=59, default=0,
    )
    time_seconds = bpy.props.IntProperty(
        name="Seconds",
        description="Seconds",
        subtype='TIME',
        min=0, max=59, default=0,
    )
    time_zone = bpy.props.FloatProperty(
        name="Time Zone",
        description="Time Zone",
        subtype='TIME',
        min=-18, max=18, default=0,
    )
    daylight_savings = bpy.props.BoolProperty(
        name="Daylight Savings Time",
        description="Daylight Savings Time",
        default=True
    )

    # generic Sun & Sky parameters
    turbidity = bpy.props.FloatProperty(
        name="Turbidity",
        description="Turbidity",
        default=0.2,
    )
    intensity = bpy.props.FloatProperty(
        name="Intensity",
        description="Intensity",
        min=0.0,
        default=1.0,
    )
    sun_glow = bpy.props.FloatProperty(
        name="Sun Glow",
        description="Sun Glow",
        default=1.0,
    )
    sun_disc = bpy.props.FloatProperty(
        name="Sun Disc",
        description="Sun Disc",
        default=0.5,
    )
    saturation = bpy.props.FloatProperty(
        name="Saturation",
        description="Saturation",
        min=0.0, max=1.0,
        default=0.5,
    )
    horizon_height = bpy.props.FloatProperty(
        name="Horizon Height",
        description="Horizon Height",
        default=0.001,
    )
    horizon_blur = bpy.props.FloatProperty(
        name="Horizon Blur",
        description="Horizon Blur",
        default=0.1,
    )

    filter_color = bpy.props.FloatVectorProperty(
        name='Filter Color', description="Filter Color",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.0, 0.0, 0.0)
    )
    ground_color = bpy.props.FloatVectorProperty(
        name='Ground Color', description="Ground Color",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.4, 0.4, 0.4)
    )

    texture_resolution = bpy.props.EnumProperty(
        name="Texture resolution",
        items=(('small', "Small", "Small - best performance"),
               ('normal', "Normal", "Normal - balance between performance and quality"),
               ('high', "High", "High - best quality")),
        description="Texture resolution",
        default='normal',
    )


@rpraddon.register_class
class RenderEnvironmentGround(bpy.types.PropertyGroup):
    enable = bpy.props.BoolProperty(
        name="Use ground",
        description="Use ground",
        default=True,
    )
    height = bpy.props.FloatProperty(
        name="Height",
        description="Height",
        default=0.0,
    )
    radius = bpy.props.FloatProperty(
        name="Radius",
        description="Radius",
        default=0.0,
    )
    shadows = bpy.props.BoolProperty(
        name="Shadows",
        description="Shadows",
        default=False,
    )
    reflection = bpy.props.BoolProperty(
        name="Reflection",
        description="Reflection",
        default=False,
    )
    reflection_color = bpy.props.FloatVectorProperty(
        name='Color', description="Reflection Color",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(1.0, 1.0, 1.0)
    )
    reflection_roughness = bpy.props.FloatProperty(
        name='Roughness', description="Reflection Roughness",
        min=0.0, default=0.5
    )
    reflection_strength = bpy.props.FloatProperty(
        name='Strength', description="Reflection Strength",
        min=0.0, default=0.5
    )


@rpraddon.register_class
class RenderEnvironment(bpy.types.PropertyGroup):
    def update_gizmo_rotation(self, context):
        if self.gizmo in bpy.data.objects:
            obj = bpy.data.objects[self.gizmo]
            obj.rotation_euler = self.gizmo_rotation

    def update_gizmo(self, context):
        if self.gizmo in bpy.data.objects:
            obj = bpy.data.objects[self.gizmo]
            self['gizmo_rotation'] = obj.rotation_euler


    gizmo_rotation = bpy.props.FloatVectorProperty(
        name='Rotation', description='Rotation',
        subtype='EULER', size=3,
        update=update_gizmo_rotation
    )

    gizmo = bpy.props.StringProperty(
        name="Gizmo",
        description="Environment Helper",
        update=update_gizmo
    )


    handle_sun_draw = None

    def switch_sun_helper(self):
        if self.enable and self.type == 'SUN_SKY' and self.sun_sky.type == 'analytical_sky':
            logging.info('draw_handler_add...')
            RenderEnvironment.handle_sun_draw = bpy.types.SpaceView3D.draw_handler_add(callback_draw_sun,
                                                                                       (self, bpy.context), 'WINDOW',
                                                                                       'POST_PIXEL')
        else:
            if RenderEnvironment.handle_sun_draw:
                logging.info('draw_handler_remove...')
                bpy.types.SpaceView3D.draw_handler_remove(RenderEnvironment.handle_sun_draw, 'WINDOW')

    def update_enable(self, context):
        self.switch_sun_helper()

    enable = bpy.props.BoolProperty(
        name="Enable RPR Environment",
        description="Enable RPR Environment",
        default=True,
        update=update_enable
    )
    type = bpy.props.EnumProperty(
        name="Environment Type",
        items=(('IBL', "IBL", "Use ProRender IBL Environment"),
               ('SUN_SKY', "Sun & Sky", "Use ProRender Sun & Sky System"),
               ),
        description="Environment Type",
        default='IBL',
        update=update_enable
    )
    ibl = bpy.props.PointerProperty(type=RenderEnvironmentIBL)  # type: RenderEnvironmentIBL
    sun_sky = bpy.props.PointerProperty(type=RenderEnvironmentSunSky)  # type: RenderEnvironmentSunSky
    ground = bpy.props.PointerProperty(type=RenderEnvironmentGround)  # type: RenderEnvironmentGround


########################################################################################################################
# Render Settings
########################################################################################################################

@rpraddon.register_class
class RenderingLimits(bpy.types.PropertyGroup):
    enable = bpy.props.BoolProperty(
        name="RenderingLimits enable name",
        description="RenderingLimits enable name desc",
        default=True
    )
    type = bpy.props.EnumProperty(
        name="Limit Type",
        items=(('TIME', "Time", "Time limit"),
               ('ITER', "Iterations", "NUmber of Iterations")
               ),
        description="When to stop rendering a frame",
        default='ITER',
    )
    iterations = bpy.props.IntProperty(
        name="Iterations count",
        description="Limit the max number of iterations for production render",
        min=0, max=0x7fffffff, default=50,
    )

    def update_time(self, context):
        print('update_time')
        seconds = self.time
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if self.hours != hours:
            self['hours'] = hours
        if self.minutes != minutes:
            self['minutes'] = minutes
        if self.seconds != seconds:
            self['seconds'] = seconds

    time = bpy.props.IntProperty(
        name="Seconds",
        description="Limit iterations seconds for production render",
        min=0, max=0x7fffffff, default=0,
        update=update_time
    )

    def update_time_from_std_time(self):
        time = self.seconds + 60 * (self.minutes + 60 * self.hours)
        if self.time != time:
            self.time = time

    def update_seconds(self, context):
        self.update_time_from_std_time()

    def update_minutes(self, context):
        self.update_time_from_std_time()

    def update_hours(self, context):
        self.update_time_from_std_time()

    hours = bpy.props.IntProperty(
        name="Hours",
        description="Limit iterations hours for production render",
        min=0, max=0x7fffffff, default=0,
        update=update_hours
    )

    minutes = bpy.props.IntProperty(
        name="Minutes",
        description="Limit iterations minutes for production render",
        min=0, max=0x7fffffff, default=0,
        soft_max=59,
        update=update_minutes
    )

    seconds = bpy.props.IntProperty(
        name="Seconds",
        description="Limit iterations seconds for production render",
        min=0, max=0x7fffffff, default=0,
        soft_max=59,
        update=update_seconds
    )


########################################################################################################################
# Anti Aliasing

@rpraddon.register_class
class AntiAliasingSettings(bpy.types.PropertyGroup):
    filter_items, _, filter_remap = create_core_enum_for_property('FILTER_', " image filter")

    filter = bpy.props.EnumProperty(
        name="Filter",
        items=filter_items,
        description="Filter Type",
        default='MITCHELL',
    )

    radius = bpy.props.FloatProperty(
        name="Filter radius",
        description="Image Filter kernel radius in pixels",
        min=0.0, max=10.0,
        default=1.5,  # each different filter type might have different default
    )

    # imagefilter_radius_params
    radius_params = {filter_name: b"imagefilter.%s.radius" % filter_name.lower().encode('ascii')
                     for filter_name in filter_remap
                     if 'NONE' != filter_name}


########################################################################################################################
# Global Illumination
########################################################################################################################
default_gi_max_ray_depth = 8


def get_gi_max_ray_depth(self):
    return self.get('max_ray_depth', default_gi_max_ray_depth)


def set_gi_max_ray_depth(self, value):
    if get_gi_max_ray_depth(self) != value:
        bpy.context.scene.rpr.render.render_quality = 'CUSTOM'
    self['max_ray_depth'] = value


@rpraddon.register_class
class GlobalIlluminationSettings(bpy.types.PropertyGroup):
    primary_solver = bpy.props.EnumProperty(
        name="Primary Solver",
        items=(('CASHED_GI', "Cashed GI", "Cashed GI"),
               ('PATH_TRACING', "Path Tracing", "Path Tracing")),
        description="Primary Solver",
        default='PATH_TRACING',
    )
    use_clamp_irradiance = bpy.props.BoolProperty(
        name="Use Clamp",
        description="Use Clamp Irradiance",
        default=False,
    )
    clamp_irradiance = bpy.props.FloatProperty(
        name="Clamp Irradiance",
        description="Clamp Irradiance",
        min=1.0, default=1.0,
    )
    max_ray_depth = bpy.props.IntProperty(
        name="Max ray depth", description="Max ray depth",
        min=0,
        soft_min=2, soft_max=50,
        default=default_gi_max_ray_depth,
        set=set_gi_max_ray_depth,
        get=get_gi_max_ray_depth,
    )


########################################################################################################################
# Post Processing
########################################################################################################################
min_color_temperature = 1000
max_color_temperature = 12000
default_color_temperature = 6500


def calc_white_balance_color(temperature):
    val = max_color_temperature - (temperature - min_color_temperature);
    return convert_K_to_RGB(val)


def get_white_balance_color(self):
    def_k = calc_white_balance_color(default_color_temperature)
    return self.get('preview_color', def_k)


def set_white_balance_color(self, value):
    self['preview_color'] = calc_white_balance_color(bpy.context.scene.rpr.render.white_balance.color_temperature)


@rpraddon.register_class
class ToneMappingSimplifiedSettings(bpy.types.PropertyGroup):
    exposure = bpy.props.FloatProperty(
        name="Exposure", description="Exposure",
        default=0.0,
    )
    contrast = bpy.props.FloatProperty(
        name="Contrast", description="Contrast",
        min=0, default=1,
    )


@rpraddon.register_class
class ToneMappingLinearSettings(bpy.types.PropertyGroup):
    iso = bpy.props.IntProperty(
        name="ISO", description="ISO",
        min=0, default=100,
    )
    shutter_speed = bpy.props.FloatProperty(
        name="Shutter Speed", description="Shutter Speed",
        min=0, default=1,
    )
    f_stop = bpy.props.FloatProperty(
        name="F-Stop", description="F-Stop",
        min=0, default=4.0,
    )


@rpraddon.register_class
class ToneMappingNonlinearSettings(bpy.types.PropertyGroup):
    burn = bpy.props.FloatProperty(
        name="Burn", description="Burn",
        min=0, default=10.0,
    )
    prescale = bpy.props.FloatProperty(
        name="Pre Scale", description="Pre Scale",
        min=0, default=0.1,
    )
    postscale = bpy.props.FloatProperty(
        name="Post Scale", description="Post Scale",
        min=0, default=1.0,
    )


@rpraddon.register_class
class ToneMappingSettings(bpy.types.PropertyGroup):
    enable = bpy.props.BoolProperty(
        name="Enable Tone Mapping",
        description="Enable Tone Mapping",
        default=False,
    )
    type = bpy.props.EnumProperty(
        name="Tone Mapping",
        items=(('simplified', "Simplified", "Simplified"),
               ('linear', "Linear", "Linear"),
               ('non_linear', "Non Linear", "Non Linear")),
        description="Tone Mapping",
        default='non_linear',
    )

    simplified = bpy.props.PointerProperty(type=ToneMappingSimplifiedSettings)  # type: ToneMappingSimplifiedSettings
    linear = bpy.props.PointerProperty(type=ToneMappingLinearSettings)  # type: ToneMappingLinearSettings
    nonlinear = bpy.props.PointerProperty(type=ToneMappingNonlinearSettings)  # type: ToneMappingNonlinearSettings


@rpraddon.register_class
class WhiteBalanceSettings(bpy.types.PropertyGroup):
    enable = bpy.props.BoolProperty(
        description="Enable White Balance",
        default=False
    )
    color_temperature = bpy.props.IntProperty(
        name="Color Temperature", description="Color Temperature (Kelvin)",
        min=min_color_temperature, max=max_color_temperature, default=default_color_temperature,
        update=set_white_balance_color
    )
    preview_color = bpy.props.FloatVectorProperty(
        name='Preview Color', description="White balance preview color",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        get=get_white_balance_color,
        set=set_white_balance_color
    )
    color_space = bpy.props.EnumProperty(
        name="Color Space",
        items=(("s_rgb", "sRGB", "sRGB", 0),
               ("adobe_rgb", "Adobe RGB", "Adobe RGB", 1),
               ("dci_p3", "DCI-P3", "DCI-P3", 2),
               ("rec_2020", "Rec. 2020", "Rec. 2020", 3)),
        description="Color Space",
        default='s_rgb'
    )
    color_space_values = dict([("s_rgb", pyrpr.COLOR_SPACE_SRGB),
                               ("adobe_rgb", pyrpr.COLOR_SPACE_ADOBE_RGB),
                               ("dci_p3", pyrpr.COLOR_SPACE_DCIP3),
                               ("rec_2020", pyrpr.COLOR_SPACE_REC2020)]
                              )


@rpraddon.register_class
class GammaCorrectionSettings(bpy.types.PropertyGroup):
    enable = bpy.props.BoolProperty(
        description="Enable Gamma Correction",
        default=True
    )
    viewport_only = bpy.props.BoolProperty(
        name="Viewport Only",
        description="Only apply gamma correction to viewport renders."
                    " Blender color management is applied to final renders.",
        default=True
    )
    display_gamma = bpy.props.FloatProperty(
        name="Display Gamma", description="Gamma correction applied to the rendered image",
        min=0, default=2.2
    )


class RPRCameraSettings:
    panorama_type = bpy.props.EnumProperty(
        name="Type",
        items=(('CUBEMAP', "Cube map", "Cube map"),
               ('SPHERICAL_PANORAMA', "Spherical", "Equirectangular/Latitude-Longtitude projection")),
        description="Projection type for panorama rendering",
        default='SPHERICAL_PANORAMA',
    )
    stereo = bpy.props.BoolProperty(
        name="Use stereo camera",
        description="Use stereo camera",
        default=False,
    )


@rpraddon.register_class
class CameraSettings(bpy.types.PropertyGroup, RPRCameraSettings):
    override_camera_settings = bpy.props.BoolProperty(
        name="Override Camera settings",
        description="Override Blender Camera settings",
        default=False,
    )


########################################################################################################################
# Depth of Field
########################################################################################################################
@rpraddon.register_class
class DofSettings(bpy.types.PropertyGroup):
    enable = bpy.props.BoolProperty(
        name="Depth of Field", description="Overwrite camera Depth of Field settings",
        default=False,
    )


def update_render_quality(self, context):
    if self.render_quality == 'HIGH':
        self.global_illumination['max_ray_depth'] = 20
    elif self.render_quality == 'LOW':
        self.global_illumination['max_ray_depth'] = 5
    elif self.render_quality == 'MEDIUM':
        self.global_illumination['max_ray_depth'] = 10


class ViewportQuality():
    fast_max_ray_depth = 5
    normal_max_ray_depth = 10


@rpraddon.register_class
class RenderSettings(bpy.types.PropertyGroup):
    if not versions.is_blender_support_aov():
        passes_aov = bpy.props.PointerProperty(type=RenderPassesAov)

    rendering_limits = bpy.props.PointerProperty(type=RenderingLimits)  # type: RenderingLimits
    aa = bpy.props.PointerProperty(type=AntiAliasingSettings)  # type: AntiAliasingSettings
    global_illumination = bpy.props.PointerProperty(type=GlobalIlluminationSettings)  # type: GlobalIlluminationSettings
    tone_mapping = bpy.props.PointerProperty(type=ToneMappingSettings)  # type: ToneMappingSettings
    white_balance = bpy.props.PointerProperty(type=WhiteBalanceSettings)  # type: WhiteBalanceSettings
    gamma_correction = bpy.props.PointerProperty(type=GammaCorrectionSettings)  # type: GammaCorrectionSettings
    camera = bpy.props.PointerProperty(type=CameraSettings)  # type: CameraSettings
    dof = bpy.props.PointerProperty(type=DofSettings)  # type: DofSettings

    render_mode, rendermode_remap = create_core_enum_property(
        None,
        'RENDER_MODE_',
        "Render Mode",
        "Render mode override",
        " render mode"
    )

    render_quality = bpy.props.EnumProperty(
        name="Render Quality",
        items=(('HIGH', "High", "Best quality, but slow render"),
               ('MEDIUM', "Medium", "Balance between quality and speed"),
               ('LOW', "Low", "Fast speed, but preview quality"),
               ('CUSTOM', "Custom", "User changed parameters")),
        description="Render Quality",
        default='CUSTOM',
        update=update_render_quality,
    )

    texturecompression = bpy.props.BoolProperty(
        name="Texture Compression",
        default=False
    )

    viewport_quality = bpy.props.EnumProperty(
        name="Viewport Quality",
        items=(('SAME_AS_RENDER', "Same as Render", "Same as render quality"),
               ('NORMAL', "Normal", "Normal"),
               ('FAST', "Fast Render", "Fast render")),
        description="Viewport Quality",
        default='FAST',
    )

    ####################################################################################################################
    # Motion Blur
    ####################################################################################################################
    motion_blur = bpy.props.BoolProperty(
        name="Motion Blur", description="Enable Motion Blur",
        default=False,
    )
    motion_blur_type = bpy.props.EnumProperty(
        name="Motion Blur Type",
        items=(('GEOMETRY', "Geometry", "Geometry"),
               ('IMAGE', "Image", "Image")),
        description="Motion Blur Type",
        default='GEOMETRY',
    )
    motion_blur_geometry_exposure = bpy.props.FloatProperty(
        name="Exposure", description="Exposure",
        min=0, default=1.0,
    )
    motion_blur_geometry_scale = bpy.props.FloatProperty(
        name="Scale", description="Scale",
        min=0, default=100.0,
    )
    motion_blur_image_exposure = bpy.props.FloatProperty(
        name="Exposure", description="Exposure",
        min=0, default=1.0,
    )
    motion_blur_image_scale = bpy.props.FloatProperty(
        name="Scale", description="Scale",
        min=0, default=100.0,
    )
    motion_blur_image_frame_start = bpy.props.IntProperty(
        name="Frame Start", description="Frame Start",
        min=0, default=0, subtype='TIME'
    )
    motion_blur_image_frame_stop = bpy.props.IntProperty(
        name="Frame Stop", description="Frame Stop",
        min=0, default=0, subtype='TIME'
    )

    def get_max_ray_depth(self, is_production):
        if not is_production:
            if self.viewport_quality == 'FAST':
                return ViewportQuality.fast_max_ray_depth
            if self.viewport_quality == 'NORMAL':
                return ViewportQuality.normal_max_ray_depth
        return self.global_illumination.max_ray_depth


########################################################################################################################
# User Settings
########################################################################################################################
from . import helpers


class UserSettings(bpy.types.PropertyGroup):
    count = len(helpers.render_resources_helper.devices)
    def_device = 'gpu' if count > 0 else 'cpu'

    device_type = bpy.props.EnumProperty(
        name="Device Type",
        items=helpers.devices_types_desc,
        description="Device Type  used for render",
        get=helpers.get_device_type,
        set=helpers.set_device_type,
        default=def_device,
        update=helpers.settings_changed,
    )

    device_type_plus_cpu = bpy.props.BoolProperty(
        name="Use CPU",
        description='Only for Production Rendering',
        default=False,
        update=helpers.settings_changed,
    )

    gpu_count = bpy.props.IntProperty(
        name="GPU Count",
        description="Number GPUs used for render",
        min=1, max=count, default=count, get=helpers.get_gpu_count, set=helpers.set_gpu_count,
        update=helpers.settings_changed,
    )

    gpu_states = bpy.props.BoolVectorProperty(name="",
                                              size=helpers.RenderResourcesHelper.max_gpu_count,
                                              default=(False, False, False, False, False, False, False, False),
                                              update=helpers.settings_changed,
                                              )

    gpu_states_inited = bpy.props.BoolProperty(
        name="Is States Inited ",
        default=False,
        update=helpers.settings_changed,
    )

    include_uncertified_devices = bpy.props.BoolProperty(name="Include Uncertified Devices",
                                                         description="Include Uncertified Devices",
                                                         default=False,
                                                         update=helpers.settings_changed,
                                                         )


    samples = bpy.props.IntProperty(
        name="Render Samples", description="The more samples, the less viewport updates for shorter render times.",
        min=1, soft_max=16, default=1,
        update=helpers.settings_changed,
    )

    notify_update_addon = bpy.props.BoolProperty(name='Notify update addon',
        default=True,
        update=helpers.settings_changed
    )


########################################################################################################################
# Developer Diagnostics
########################################################################################################################

def init_trace_dump(dev_settings):
    path = dev_settings.get_trace_dump_folder()
    if dev_settings.trace_dump:
        logging.info('tracing: on (%s)' % path)
        pyrpr.ContextSetParameter1u(ffi.NULL, b"tracing", 0)
        try:
            if not os.path.isdir(path):
                os.makedirs(path)
        except IOError:
            logging.info("trace dump folder can't be set: %s, set default folder" % path)
            dev_settings['trace_dump_folder'] = ''
            path = dev_settings.get_trace_dump_folder()
            try:
                if not os.path.isdir(path):
                    os.makedirs(path)
            except IOError:
                dev_settings['trace_dump_folder'] = ''
                dev_settings['trace_dump'] = False
                return

        pyrpr.ContextSetParameterString(ffi.NULL, b"tracingfolder", path.encode('latin1'))
        pyrpr.ContextSetParameter1u(ffi.NULL, b"tracing", 1)
    else:
        pyrpr.ContextSetParameter1u(ffi.NULL, b"tracing", 0)
        logging.info('tracing: off')


def update_trace_dump_params(self, context):
    init_trace_dump(self)


@rpraddon.register_class
class DeveloperSettings(bpy.types.PropertyGroup):
    def get_trace_dump_folder(self):
        if self.trace_dump_folder != '':
            return bpy.path.abspath(self.trace_dump_folder)
        else:
            return str(Path(rprblender.__file__).parent / '.core_trace')

    log = bpy.props.BoolProperty(
        name="Enable Error Logging", description="Enable Error Logging",
        default=False,
    )
    clear_log_every = bpy.props.IntProperty(
        name="Clear logfile every (days)", description="Clear logfile every (days)",
        min=0, soft_max=30, default=10,
    )
    trace_dump = bpy.props.BoolProperty(
        name="Trace Dump", description="Enable Trace Dump",
        default=False,
        update=update_trace_dump_params,
    )
    trace_dump_folder = bpy.props.StringProperty(
        name='Trace Dump Folder', description='Trace Dump Folder', subtype='DIR_PATH',
        update=update_trace_dump_params,
    )
    export_model = bpy.props.BoolProperty(
        name="Export Model", description="Enable Export Model",
        default=False,
    )
    export_model_file = bpy.props.StringProperty(
        name='Export Model File', description='Export Model File', subtype='FILE_PATH'
    )


@rpraddon.register_class
class ThumbnailsSettings(bpy.types.PropertyGroup):

    warning = "Enabling thumbnails may cause stability (or performance) issues and would break blender autosaves."

    def enable_change(self, context):
        if self.enable:
            bpy.ops.wm.rpr_thumbnail_update_caller_operator()
            logging.debug('Thumbnails is an experimental feature. ' + self.warning)
        else:
            bpy.ops.wm.rpr_thumbnail_update_caller_disable_operator()

    enable = bpy.props.BoolProperty(
        name="Enable Thumbnails",
        description=warning,
        default=False,
        update=enable_change
    )

    use_large_preview = bpy.props.BoolProperty(
        name="Use Large Preview",
        description="Use Large Preview",
        default=False,
    )


########################################################################################################################
# RPR Settings
########################################################################################################################
@rpraddon.register_class
class RPRRenderSettings(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.Scene.rpr = bpy.props.PointerProperty(
            name="Radeon ProRender Settings",
            description="Radeon ProRender render settings",
            type=cls,
        )

        cls.saved_addon_version = bpy.props.IntVectorProperty(name="Version")

        cls.render = bpy.props.PointerProperty(type=RenderSettings)  # type: RenderSettings
        cls.fake_user_settings = bpy.props.PointerProperty(type=UserSettings)  # without installed addon
        cls.dev = bpy.props.PointerProperty(type=DeveloperSettings)  # type: DeveloperSettings


        cls.render_preview = bpy.props.PointerProperty(type=RenderSettings)
        cls.preview_environment = bpy.props.PointerProperty(type=RenderEnvironment)  # type: RenderEnvironment
        cls.preview_aov = bpy.props.PointerProperty(type=RenderPassesAov)

        cls.render_thumbnail = bpy.props.PointerProperty(type=RenderSettings)
        cls.thumbnails = bpy.props.PointerProperty(type=ThumbnailsSettings)  # type: ThumbnailsSettings
        cls.thumbnails_aov = bpy.props.PointerProperty(type=RenderPassesAov)

        ################################################################################################################
        # Settings
        ################################################################################################################
        cls.use_render_stamp = bpy.props.BoolProperty(
            name="Use Render Stamp",
            description="Use Render Stamp",
            default=False,
        )
        cls.render_stamp = bpy.props.StringProperty(
            name="Render Stamp",
            description="\
            Render stamp: \n\
            %pt - performance time \n\
            %pp - performance passes \n\
            %sl - scene lights \n\
            %so - scene objects \n\
            %c - CPU \n\
            %g - GPU \n\
            %r - rendering mode \n\
            %h - hardware for rendering \n\
            %i - computer name  \n\
            %d - current date \n\
            %b - build number",
            default="Radeon ProRender for Blender %b | %h | Time: %pt | Passes: %pp | Objects: %so | Lights: %sl",
        )

        cls.copy_textures = bpy.props.EnumProperty(
            name="Copy textures",
            items=(('DEFAULT', "Don't copy textures", "Reference original texture images of material library"),
                   ('LOCAL', "Copy textures locally", "Copy texture images under blend file folder")),
            description="Choose to copy texture images to blend file folder",
            default='DEFAULT',
        )

    @classmethod
    def unregister(cls):
        del bpy.types.Scene.rpr


@rpraddon.register_class
class RPRObject(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.Object.rpr_object = bpy.props.PointerProperty(
            name="RPR Object",
            description="RPR Material params",
            type=cls,
        )

        cls.shadowcatcher = bpy.props.BoolProperty(
            name="Shadow Catcher",
            description="Use this object as shadowcatcher",
            default=False,
        )

        cls.shadows = bpy.props.BoolProperty(
            name="Shadows",
            description="Enable shadows for this object",
            default=True,
        )

        cls.portallight = bpy.props.BoolProperty(
            name="Portal Light",
            description="Use this object as portallight",
            default=False,
        )

        cls.subdivision = bpy.props.IntProperty(
            name="Subdivision",
            description="Subdivision factor for mesh",
            default=0,
            min=0,
        )

        cls.subdivision_boundary = bpy.props.EnumProperty(
            name="Boundary",
            items=helpers.subdivision_boundary_prop.items,
            description="Boundary",
            default='EDGE_ONLY',
        )

        cls.subdivision_crease_weight = bpy.props.FloatProperty(
            name="Subdivision Weight",
            description="Subdivision interop for mesh",
            default=1.0,
            min=0,
        )

        cls.visibility_in_primary_rays = bpy.props.BoolProperty(
            name="Visibility, In Primary Rays",
            description="If objects is visible in camera rays",
            default=True,
        )



@rpraddon.register_class
class RPRCamera(bpy.types.PropertyGroup, RPRCameraSettings):
    @classmethod
    def register(cls):
        bpy.types.Camera.rpr_camera = bpy.props.PointerProperty(
            name="RPR Camera",
            description="RPR Camera params",
            type=cls,
        )


import bpy
from bpy.types import Operator, AddonPreferences


class RPRAddonPreferences(AddonPreferences):
    bl_idname = __package__
    settings = bpy.props.PointerProperty(type=UserSettings)


@rpraddon.register_class
class RPRLamp(bpy.types.PropertyGroup):
    intensity = bpy.props.FloatProperty(
        name="Intensity",
        description="Intensity in Watts for Point/Spot/Area light and W/m2 for Sun",
        min=0.0, default=100.0,
    )

    @classmethod
    def register(cls):
        bpy.types.Lamp.rpr_lamp = bpy.props.PointerProperty(
            name="RPR Lamp",
            description="RPR Lamp params",
            type=cls,
        )
        cls.ies_file_name = bpy.props.StringProperty(
            name='IES Data file', description='IES Data file name',
            default='',
        )

    @classmethod
    def unregister(cls):
        del bpy.types.Lamp.rpr_lamp


@rpraddon.register_class
class RPRWorldData(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.World.rpr_data = bpy.props.PointerProperty(
            name="RPR Data",
            type=cls,
        )
        cls.environment = bpy.props.PointerProperty(type=RenderEnvironment)

    @classmethod
    def unregister(cls):
        del bpy.types.World.rpr_data

@rpraddon.register_class
class RPRSceneRenderLayerData(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.SceneRenderLayer.rpr_data = bpy.props.PointerProperty(
            name="RPR Data",
            type=cls,
        )
        if versions.is_blender_support_aov():
            cls.passes_aov = bpy.props.PointerProperty(type=RenderPassesAov)

    @classmethod
    def unregister(cls):
        del bpy.types.SceneRenderLayer.rpr_data

def register():
    logging.debug("properties.register()")
    bpy.utils.register_class(UserSettings)
    bpy.utils.register_class(RPRAddonPreferences)


def unregister():
    logging.debug("properties.unregister()")
    bpy.utils.unregister_class(RPRAddonPreferences)
    bpy.utils.unregister_class(UserSettings)
