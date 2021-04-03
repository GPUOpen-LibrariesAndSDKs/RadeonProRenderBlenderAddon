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
import math
import sys
import os

import bpy
import pyrpr
import pyhybrid
import pyrpr2

from bpy.props import (
    BoolProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    BoolVectorProperty,
    EnumProperty,
    StringProperty,
    IntVectorProperty
)
import platform

from rprblender import utils
from rprblender.utils.user_settings import get_user_settings, on_settings_changed
from . import RPR_Properties
from rprblender.engine import context

from rprblender.utils import logging
log = logging.Log(tag='properties.render')


class RPR_RenderLimits(bpy.types.PropertyGroup):
    """ Properties for render limits: 
        we use both a time and a max sample limit.
        if noise threshold > 0 then use adaptive sampling.
    """

    min_samples: IntProperty(
        name="Min Samples",
        description="Minimum number of samples to render for each pixel. After this, adaptive "
                    "sampling will stop sampling pixels where noise is less than threshold",
        min=16, default=64,
    )

    max_samples: IntProperty(
        name="Max Samples",
        description="Number of iterations to render for each pixel",
        min=16, default=128,
    )

    noise_threshold: FloatProperty(
        name="Noise Threshold",
        description="Cutoff for adaptive sampling. Once pixels are below this amount of noise, "
                    "no more samples are added.  Set to 0 for no cutoff",
        min=0.0, default=.05, max=1.0,
    )

    adaptive_tile_size: IntProperty(
        name="Adaptive tile size",
        min=4, default=16, max=64
    )

    update_samples: IntProperty(
        name="Samples per View Update",
        description="The more samples, the less intermediate render result updates for shorter "
                    "render times",
        min=1, default=4,
    )

    update_samples_rpr2: IntProperty(
        name="Samples per View Update",
        description="The more samples, the less intermediate render result updates for shorter "
                    "render times",
        min=1, default=32,
    )

    seconds: IntProperty(
        name="Time Limit",
        description="Limit rendering process in seconds. 0 - means limit by number of samples",
        min=0, default=0
    )

    preview_samples: IntProperty(
        name="Preview Samples",
        description="Material and light previews number of samples to render for each pixel",
        min=16, default=64,
    )

    preview_update_samples: IntProperty(
        name="Samples per Preview Update",
        description="The more samples, the less intermediate preview render result updates for "
                    "shorter render times",
        min=1, default=4,
    )

    def set_adaptive_params(self, rpr_context):
        """
        Set the adaptive sampling parameters for this context.
        adaptive_threshold, adaptive_min_samples, and adaptive_tile_size
        """
        res = False
        res |= rpr_context.set_parameter(pyrpr.CONTEXT_ADAPTIVE_SAMPLING_TILE_SIZE, self.adaptive_tile_size)
        res |= rpr_context.set_parameter(pyrpr.CONTEXT_ADAPTIVE_SAMPLING_MIN_SPP, self.min_samples)
        res |= rpr_context.set_parameter(pyrpr.CONTEXT_ADAPTIVE_SAMPLING_THRESHOLD, self.noise_threshold)
        return res


class RPR_RenderDevices(bpy.types.PropertyGroup):
    """ Properties for render devices: CPU, GPUs """

    def update_states(self, context):
        if len(pyrpr.Context.gpu_devices) > 0:
            # selecting first gpu if no gpu and cpu is selected
            if not any(self.gpu_states) and not self.cpu_state:
                self.gpu_states[0] = True
        else:
            # if no GPU then cpu always should be enabled
            self.cpu_state = True
        on_settings_changed(self, context)

        # after changing devices its good to reset PreviewEngine and
        # PreviewEngine.rpr_context will be created with updated devices
        from rprblender.engine.preview_engine import PreviewEngine
        PreviewEngine.reset()

    gpu_states: BoolVectorProperty(
        name="",
        description="Use GPU device for rendering",
        size=16,
        # Only first GPU is enabled by default
        default=tuple(i == 0 and bool(pyrpr.Context.gpu_devices) for i in range(16)),
        update=update_states
    )
    cpu_state: BoolProperty(
        name="",
        description="Use CPU device for rendering",
        default=not pyrpr.Context.gpu_devices,  # True if no GPUs are available
        update=update_states
    )
    cpu_threads: IntProperty(
        name="CPU Threads",
        description="Number of CPU threads for render, optimal value is about the number of physical CPU cores",
        min=1, max=utils.get_cpu_threads_number(),
        default=utils.get_cpu_threads_number(),
        update=on_settings_changed,
    )

    @property
    def available_gpu_states(self):
        return (self.gpu_states[i] for i in range(len(pyrpr.Context.gpu_devices)))

    def count(self):
        res = int(self.cpu_state)
        res += sum(int(state) for state in self.available_gpu_states)
        return res

    def has_gpu(self):
        return any(bool(state) for state in self.available_gpu_states)


class RPR_UserSettings(bpy.types.PropertyGroup):
    """
    Specific user settings stored in Blender User Settings in standalone mode.
    Saved in Scene in debug mode.
    """
    final_devices: PointerProperty(type=RPR_RenderDevices)
    viewport_devices: PointerProperty(type=RPR_RenderDevices)

    separate_viewport_devices: BoolProperty(
        name="Separate Viewport Devices",
        description="Use separate viewport and preview render devices configuration",
        default=False,
        update=on_settings_changed,
    )

    collect_stat: BoolProperty(
        name="Collect anonymous render statistics",
        description="Statistics of render time, and scene details will be collated and "
                    "anonymously sent to AMD for plugin improvement. "
                    "No personal information is collected",
        default=True,
        update=on_settings_changed,
    )

    use_gl_interop: BoolProperty(
        name="OpenGL interoperability",
        description="Use OpenGL interoperability in viewport. This should speedup viewport rendering. "
                    "However, to use an external GPU for viewport rendering this should be disabled",
        default=True,
        update=on_settings_changed,
    )

    bake_resolution: EnumProperty(
        name="Texture Resolution",
        description="Texture resolution to use for nodes baking",
        items=(
            ('64', '64', '64'),
            ('128', '128', '128'),
            ('256', '256', '256'),
            ('512', '512', '512'),
            ('1024', '1024', '1024'),
            ('2048', '2048', '2048'),
            ('4096', '4096', '4096')
        ),
        default='2048',
    )

    adapt_viewport_resolution: BoolProperty(
        name="Adapt Viewport Resolution",
        description="Adapts Viewport Resolution for interactivity",
        default=True,
    )

    viewport_samples_per_sec: IntProperty(
        name="Samples Per Second",
        description="Viewport samples per second",
        min=1, soft_max=200, default=15,
    )

    min_viewport_resolution_scale: IntProperty(
        name="Min Resolution Scale",
        description="Min adapt viewport resolution scale",
        subtype='PERCENTAGE',
        min=5, max=100, default=25,
    )

    viewport_denoiser_upscale: BoolProperty(
        name="Viewport Denoising and Upscaling",
        description="Denoise rendered image with Machine Learning denoiser.\n"
                    "Rendering at 2 times lower resoluting then upscaling rendered image "
                    "in the end of render",
        default=True if not utils.IS_MAC else False, # TODO remove when macos upscaler fixed
    )


class RPR_RenderProperties(RPR_Properties):
    """ Main render properties. Available from scene.rpr """

    saved_addon_version: bpy.props.IntVectorProperty(
        name="Version"
    )

    # RENDER DEVICES for development debug mode; standalone settings are saved as addon properties
    debug_user_settings: PointerProperty(type=RPR_UserSettings)

    # DEBUG OPTIONS
    def update_log_min_level(self, context):
        logging.limit_log('default', getattr(logging, self.log_min_level))

    log_min_level: EnumProperty(
        name="Log Min Level",
        description="Log minimum level",
        items=(
            ('DEBUG', "Debug", "Show all log: Debug, Info, Warning, Error"),
            ('INFO', "Info", "Show log: Info, Warning, Error"),
            ('WARN', "Warning", "Show log: Warning, Error"),
            ('ERROR', "Error", "Show log: Error"),
        ),
        default='INFO',
        update=update_log_min_level
    )
    trace_dump: BoolProperty(
        name="Trace Dump",
        description="Enable Trace Dump",
        default=False
    )
    trace_dump_folder: StringProperty(
        name='Trace Dump Folder',
        description='Trace Dump Folder',
        subtype='DIR_PATH',
        default=str(utils.get_temp_dir() / "tracedump")
    )
    texture_cache_dir: StringProperty(
        name='Texture Cache Dir',
        description='Dirctory used for texture cache',
        subtype='DIR_PATH',
        default=str(utils.package_root_dir() / ".tex_cache")
    )

    # RENDER LIMITS
    limits: PointerProperty(type=RPR_RenderLimits)
    viewport_limits: PointerProperty(type=RPR_RenderLimits)

    # RENDER TILES
    use_tile_render: BoolProperty(
        name="Tiled rendering",
        description="Use tiles to do final rendering. Available with Legacy render quality only",
        default=False,
    )
    tile_x: IntProperty(
        name="Tile X", description="Horizontal tile size to use while rendering",
        min=32, max=2048,
        default=512,
    )
    tile_y: IntProperty(
        name="Y", description="Vertical tile size to use while rendering",
        min=32, max=2048,
        default=512,
    )
    tile_order: EnumProperty(
        name="Tile Order",
        items=(
            ('CENTER_SPIRAL', "Center Spiral", "Render from center by spiral"),
            ('VERTICAL', "Vertical", "Render from vertically from left to right"),
            ('HORIZONTAL', "Horizontal", "Render horizontally from top to bottom"),
        ),
        default='CENTER_SPIRAL'
    )

    @property
    def is_tile_render_available(self):
        return self.use_tile_render and self.render_quality in ('FULL', 'FULL2')

    # RAY DEPTH PROPERTIES
    use_clamp_radiance: BoolProperty(
        name="Clamp",
        description="Use clamp radiance",
        default=False,
    )
    clamp_radiance: FloatProperty(
        name="Clamp Radiance",
        description="Clamp radiance",
        min=1.0, default=1.0,
    )
    max_ray_depth: IntProperty(
        name="Total", description="Max total ray depth",
        min=0, soft_min=2, soft_max=50,
        default=8,
    )
    diffuse_depth: IntProperty(
        name="Diffuse", description="Diffuse ray depth",
        min=0, soft_min=2, soft_max=50,
        default=3,
    )
    glossy_depth: IntProperty(
        name="Glossy", description="Glossy ray depth",
        min=0, soft_min=2, soft_max=50,
        default=5,
    )
    shadow_depth: IntProperty(
        name="Shadow", description="Shadow depth",
        min=0, soft_min=2, soft_max=50,
        default=5,
    )
    refraction_depth: IntProperty(
        name="Refraction", description="Refraction ray depth",
        min=0, soft_min=2, soft_max=50,
        default=5,
    )
    glossy_refraction_depth: IntProperty(
        name="Glossy Refraction", description="Glossy refraction ray depth",
        min=0, soft_min=2, soft_max=50,
        default=5,
    )
    ray_cast_epsilon: FloatProperty(
        name="Ray Cast Epsilon (mm)", description="Ray cast epsilon (in millimeters)",
        min=0.0, soft_max=2.0,
        default=0.02,
    )

    # RENDER EFFECTS
    use_render_stamp: BoolProperty(
        name="Render Stamp",
        description="Use render stamp",
        default=False
    )
    render_stamp: StringProperty(
        name="Render Stamp",
        description="\
        Render stamp: \n\
        %pt - performance time \n\
        %pp - performance samples \n\
        %sl - scene lights \n\
        %so - scene objects \n\
        %c - CPU \n\
        %g - GPU \n\
        %r - rendering mode \n\
        %h - hardware for rendering \n\
        %i - computer name  \n\
        %d - current date \n\
        %b - build number",
        default="Radeon ProRender for Blender %b | %h | Time: %pt | Samples: %pp | Objects: %so | Lights: %sl",
    )

    render_mode: EnumProperty(
        name="Render Mode",
        description="Override render mode",
        items=(
            ('GLOBAL_ILLUMINATION', "Global Illumination", "Global illumination render mode"),
            ('DIRECT_ILLUMINATION', "Direct Illumination", "Direct illumination render mode"),
            ('DIRECT_ILLUMINATION_NO_SHADOW', "Direct Illumination no Shadows", "Direct illumination without shadows render mode"),
            ('WIREFRAME', "Wireframe", "Wireframe render mode"),
            ('MATERIAL_INDEX', "Material Index", "Material index render mode"),
            ('POSITION', "World Position", "World position render mode"),
            ('NORMAL', "Shading Normal", "Shading normal render mode"),
            ('TEXCOORD', "Texture Coordinate", "Texture coordinate render mode"),
            ('AMBIENT_OCCLUSION', "Ambient Occlusion", "Ambient occlusion render mode"),
            ('DIFFUSE', "Diffuse", "Diffuse render mode"),
        ),
        default='GLOBAL_ILLUMINATION',
    )

    pixel_filter: EnumProperty(
        name="Pixel Filter",
        description="Filter used for anti aliasing",
        items=(
            ('BOX', "Box", "Box Filter"),
            ('TRIANGLE', "Triangle", "Triangle Filter"),
            ('GAUSSIAN', "Gaussian", "Gaussian Filter"),
            ('MITCHELL', "Mitchell", "Mitchell Filter"),
            ('LANCZOS', "Lanczos", "Lanczos Filter"),
            ('BLACKMANHARRIS', "Blackman-Harris", "Blackman-Harris Filter"),
        ),
        default='BLACKMANHARRIS',
    )

    pixel_filter_width: FloatProperty(
        name="Width", description="Pixel Filter Width",
        min=0, soft_max=5,
        default=1.5,
    )

    render_quality_items = [
        ('FULL2', "Full", "Full render quality using RPR 2, including hardware ray tracing support"),
        ('FULL', "Legacy", "Full render quality using RPR 1")
    ]
    if pyhybrid.enabled:
        render_quality_items += [
            ('HIGH', "High", "High render quality"),
            ('MEDIUM', "Medium", "Medium render quality"),
            ('LOW', "Low", "Low render quality"),
        ]

    def update_render_quality(self, context):
        if self.render_quality in ('FULL', 'FULL2'):
            return

        settings = get_user_settings()
        settings.final_devices.cpu_state = False
        settings.viewport_devices.cpu_state = False

    render_quality: EnumProperty(
        name="Render Quality",
        description="RPR render quality",
        items=render_quality_items,
        default='FULL2',
        update=update_render_quality
    )

    hybrid_low_mem: BoolProperty(
        name="Use 4GB memory",
        description="Enable to support GPUs with 4Gb VRAM or less",
        default=False,
    )

    motion_blur_in_velocity_aov: BoolProperty(
        name="Only in Velocity AOV",
        description="Apply Motion Blur in Velocity AOV only\nOnly for Full render quality",
        default=False,
    )

    # CONTOUR render mode settings
    use_contour_render: BoolProperty(
        name="Contour",
        description="Use Contour rendering mode. Final render only",
        default=False
    )

    contour_use_object_id: BoolProperty(
        name="Use Object ID",
        description="Use Object ID for Contour rendering",
        default=True,
    )
    contour_use_material_id: BoolProperty(
        name="Use Material Index",
        description="Use Material Index for Contour rendering",
        default=True,
    )
    contour_use_shading_normal: BoolProperty(
        name="Use Shading Normal",
        description="Use Shading Normal for Contour rendering",
        default=True,
    )

    contour_object_id_line_width: FloatProperty(
        name="Line Width Object",
        description="Line width for Object ID contours",
        min=1.0, max=10.0,
        default=1.0,
    )
    contour_material_id_line_width: FloatProperty(
        name="Line Width Material",
        description="Line width for Material Index contours",
        min=1.0, max=10.0,
        default=1.0,
    )
    contour_shading_normal_line_width: FloatProperty(
        name="Line Width Normal",
        description="Line width for Shading Normal contours",
        min=1.0, max=10.0,
        default=1.0,
    )

    contour_normal_threshold: FloatProperty(
        name="Normal Threshold",
        description="Threshold for normals, in degrees",
        subtype='ANGLE',
        min=0.0, max=math.radians(180.0),
        default=math.radians(45.0),
    )
    contour_antialiasing: FloatProperty(
        name="Antialiasing",
        min=0.0, max=1.0,
        default=1.0,
    )

    contour_debug_flag: BoolProperty(
        name="Feature Debug",
        default=False,
    )

    def init_rpr_context(self, rpr_context, is_final_engine=True, use_gl_interop=False, use_contour_integrator=False):
        """ Initializes rpr_context by device settings """

        scene = self.id_data
        log("Syncing scene: %s" % scene.name)

        devices = self.get_devices(is_final_engine)

        context_flags = set()
        # enable CMJ sampler for adaptive sampling
        context_props = [pyrpr.CONTEXT_SAMPLER_TYPE, pyrpr.CONTEXT_SAMPLER_TYPE_CMJ]

        if devices.cpu_state:
            context_flags |= {pyrpr.Context.cpu_device['flag']}
            context_props.extend([pyrpr.CONTEXT_CPU_THREAD_LIMIT, devices.cpu_threads])

        metal_enabled = False
        for i, gpu_state in enumerate(devices.available_gpu_states):
            if gpu_state:
                context_flags |= {pyrpr.Context.gpu_devices[i]['flag']}
                if use_gl_interop:
                    context_flags |= {pyrpr.CREATION_FLAGS_ENABLE_GL_INTEROP}

                if not metal_enabled and platform.system() == 'Darwin'\
                        and not isinstance(rpr_context, context.RPRContext2):
                    # only enable metal once and if a GPU is turned on
                    metal_enabled = True
                    context_flags |= {pyrpr.CREATION_FLAGS_ENABLE_METAL}

        if self.render_quality in ('LOW', 'MEDIUM', 'HIGH') and self.hybrid_low_mem:
            # set these props to use < 4gb
            vertex_mem_size = pyrpr.ffi.new('int*', 768 * 1024 * 1024)  # 768mb texture memory
            acc_mem_size = pyrpr.ffi.new('int*', 1024 ** 3)             # 1gb for bvh memry
            context_props.extend([
                pyrpr.CONTEXT_CREATEPROP_HYBRID_VERTEX_MEMORY_SIZE, vertex_mem_size,
                pyrpr.CONTEXT_CREATEPROP_HYBRID_ACC_MEMORY_SIZE, acc_mem_size])
               
        context_props.append(0) # should be followed by 0

        if self.trace_dump:
            if not os.path.isdir(self.trace_dump_folder):
                os.mkdir(self.trace_dump_folder)

            pyrpr.Context.set_parameter(None, pyrpr.CONTEXT_TRACING_PATH, self.trace_dump_folder)
            pyrpr.Context.set_parameter(None, pyrpr.CONTEXT_TRACING_ENABLED, True)
        else:
            pyrpr.Context.set_parameter(None, pyrpr.CONTEXT_TRACING_ENABLED, False)

        rpr_context.init(context_flags, context_props, use_contour_integrator=use_contour_integrator)

        if metal_enabled:
            mac_vers_major = platform.mac_ver()[0].split('.')[1]
            # if this is mojave turn on MPS
            if float(mac_vers_major) >= 14:
                rpr_context.set_parameter(pyrpr.CONTEXT_METAL_PERFORMANCE_SHADER, 1)

        # enable texture cache for RPR2
        if isinstance(rpr_context, context.RPRContext2):
            if not os.path.isdir(self.texture_cache_dir):
                os.mkdir(self.texture_cache_dir)
            rpr_context.set_parameter(pyrpr.CONTEXT_TEXTURE_CACHE_PATH, self.texture_cache_dir)

            # set ocio config file to blender included one
            # TODO can use blender render set render space, and check for custom ocio setting
            rpr_context.set_parameter(pyrpr.CONTEXT_OCIO_CONFIG_PATH, 
                                      os.path.join(bpy.utils.resource_path('LOCAL'),
                                                   'datafiles', 'colormanagement',
                                                   'config.ocio'))
            rpr_context.set_parameter(pyrpr.CONTEXT_OCIO_RENDERING_COLOR_SPACE, 
                                      "Linear")

    def get_devices(self, is_final_engine=True):
        """ Get render devices settings for current mode """
        devices_settings = get_user_settings()
        if is_final_engine or not devices_settings.separate_viewport_devices:
            return devices_settings.final_devices
        return devices_settings.viewport_devices

    def export_ray_depth(self, rpr_context):
        """ Exports ray depth settings """

        res = False

        res |= rpr_context.set_parameter(pyrpr.CONTEXT_MAX_RECURSION, self.max_ray_depth)
        res |= rpr_context.set_parameter(pyrpr.CONTEXT_MAX_DEPTH_DIFFUSE, self.diffuse_depth)
        res |= rpr_context.set_parameter(pyrpr.CONTEXT_MAX_DEPTH_GLOSSY, self.glossy_depth)
        res |= rpr_context.set_parameter(pyrpr.CONTEXT_MAX_DEPTH_SHADOW, self.shadow_depth)
        res |= rpr_context.set_parameter(pyrpr.CONTEXT_MAX_DEPTH_REFRACTION, self.refraction_depth)
        res |= rpr_context.set_parameter(pyrpr.CONTEXT_MAX_DEPTH_GLOSSY_REFRACTION, self.glossy_refraction_depth)
        res |= rpr_context.set_parameter(pyrpr.CONTEXT_RADIANCE_CLAMP, self.clamp_radiance if \
            self.use_clamp_radiance else sys.float_info.max)

        res |= rpr_context.set_parameter(pyrpr.CONTEXT_RAY_CAST_EPISLON,
                                         self.ray_cast_epsilon * 0.001) # Convert millimeters to meters

        return res

    def export_render_mode(self, rpr_context):
        return rpr_context.set_parameter(pyrpr.CONTEXT_RENDER_MODE,
                                         getattr(pyrpr, 'RENDER_MODE_' + self.render_mode))

    def is_contour_available(self, is_final_engine):
        devices = self.get_devices(is_final_engine=is_final_engine)
        return self.render_quality == 'FULL2' and not devices.cpu_state

    def is_contour_used(self, is_final_engine=True):
        return self.is_contour_available(is_final_engine) and self.use_contour_render

    def export_contour_mode(self, rpr_context):
        """ set Contour render mode parameters """
        rpr_context.set_parameter(pyrpr.CONTEXT_CONTOUR_USE_OBJECTID, self.contour_use_object_id)
        rpr_context.set_parameter(pyrpr.CONTEXT_CONTOUR_USE_MATERIALID, self.contour_use_material_id)
        rpr_context.set_parameter(pyrpr.CONTEXT_CONTOUR_USE_NORMAL, self.contour_use_shading_normal)

        rpr_context.set_parameter(pyrpr.CONTEXT_CONTOUR_LINEWIDTH_OBJECTID, self.contour_object_id_line_width)
        rpr_context.set_parameter(pyrpr.CONTEXT_CONTOUR_LINEWIDTH_MATERIALID, self.contour_material_id_line_width)
        rpr_context.set_parameter(pyrpr.CONTEXT_CONTOUR_LINEWIDTH_NORMAL, self.contour_shading_normal_line_width)

        rpr_context.set_parameter(pyrpr.CONTEXT_CONTOUR_NORMAL_THRESHOLD, math.degrees(self.contour_normal_threshold))
        rpr_context.set_parameter(pyrpr.CONTEXT_CONTOUR_ANTIALIASING, self.contour_antialiasing)

        rpr_context.set_parameter(pyrpr.CONTEXT_CONTOUR_DEBUG_ENABLED, self.contour_debug_flag)

        rpr_context.enable_aov(pyrpr.AOV_OBJECT_ID)
        rpr_context.enable_aov(pyrpr.AOV_MATERIAL_ID)
        rpr_context.enable_aov(pyrpr.AOV_SHADING_NORMAL)

    def export_pixel_filter(self, rpr_context):
        """ Exports pixel filter settings """
        filter_type = getattr(pyrpr, f"FILTER_{self.pixel_filter}")
        filter_radius = getattr(pyrpr, f"CONTEXT_IMAGE_FILTER_{self.pixel_filter}_RADIUS")

        res = False
        res |= rpr_context.set_parameter(pyrpr.CONTEXT_IMAGE_FILTER_TYPE, filter_type)
        res |= rpr_context.set_parameter(filter_radius, self.pixel_filter_width)
        return res

    def export_render_quality(self, rpr_context):
        if self.render_quality == 'FULL':
            return False

        quality = getattr(pyrpr, 'RENDER_QUALITY_' + self.render_quality)
        return rpr_context.set_parameter(pyrpr.CONTEXT_RENDER_QUALITY, quality)

    @classmethod
    def register(cls):
        log("Register")
        bpy.types.Scene.rpr = PointerProperty(
            name="RPR Render Settings",
            description="RPR render settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Unregister")
        del bpy.types.Scene.rpr
