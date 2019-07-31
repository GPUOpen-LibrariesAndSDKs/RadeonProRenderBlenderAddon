import sys
import os

import bpy
import pyrpr
from bpy.props import (
    BoolProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    BoolVectorProperty,
    EnumProperty,
    StringProperty,
)
import platform

from rprblender import utils
from rprblender.utils.user_settings import get_user_settings, on_settings_changed
from . import RPR_Properties

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
                    "sampling will stop sampling pixels where noise is less than threshold.",
        min=16, default=64,
    )

    max_samples: IntProperty(
        name="Max Samples",
        description="Number of iterations to render for each pixel.",
        min=16, default=64,
    )

    noise_threshold: FloatProperty(
        name="Noise Threshold",
        description="Cutoff for adaptive sampling. Once pixels are below this amount of noise, "
                    "no more samples are added.  Set to 0 for no cutoff.",
        min=0.0, default=.05, max=1.0,
    )

    adaptive_tile_size: IntProperty(
        name="Adaptive tile size",
        min=4, default=16, max=16
    )

    update_samples: IntProperty(
        name="Samples per View Update",
        description="The more samples, the less intermediate render result updates for shorter "
                    "render times",
        min=1, default=4,
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

    limit_viewport_resolution: BoolProperty(
        name="Limit Viewport Resolution",
        description="Limits viewport resolution to final render resolution",
        default=True,
    )

    def set_adaptive_params(self, rpr_context):
        """
        Set the adaptive sampling parameters for this context.
        adaptive_threshold, adaptive_min_samples, and adaptive_tile_size
        """
        res = False
        res |= rpr_context.set_parameter('as.tilesize', self.adaptive_tile_size)
        res |= rpr_context.set_parameter('as.minspp', self.min_samples)
        res |= rpr_context.set_parameter('as.threshold', self.noise_threshold)
        return res


# Getting list of available devices for RPR_RenderDevices
enum_devices = [('CPU', "CPU", "Use CPU for rendering"),]
if len(pyrpr.Context.gpu_devices) > 0:
    enum_devices.insert(0, ('GPU', "GPU", "Use GPU device for rendering"))
    enum_devices.append(('GPU+CPU', "GPU+CPU", "Use GPU+CPU devices for rendering"))


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

    if len(pyrpr.Context.gpu_devices) > 0:
        gpu_states: BoolVectorProperty(
            name="",
            description="Use GPU device for rendering",
            size=len(pyrpr.Context.gpu_devices),
            default=tuple(i == 0 for i in range(len(pyrpr.Context.gpu_devices))), # Only first GPU is enabled by default
            update=update_states
        )

    cpu_state: BoolProperty(
        name=pyrpr.Context.cpu_device['name'],
        description="Use CPU device for rendering",
        default=len(pyrpr.Context.gpu_devices) == 0, # True if no GPUs are available
        update=update_states
    )
    cpu_threads: IntProperty(
        name="CPU Threads",
        description="Number of CPU threads for render, optimal value is about the number of physical CPU cores",
        min=1, max=utils.get_cpu_threads_number(),
        default=utils.get_cpu_threads_number(),
        update=on_settings_changed,
    )

    def count(self):
        res = int(self.cpu_state)
        if hasattr(self, 'gpu_states'):
            res += sum(bool(state) for state in self.gpu_states)
        return res


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
                    "No personal information is collected.",
        default=True,
        update=on_settings_changed,
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

    # RENDER LIMITS
    limits: PointerProperty(type=RPR_RenderLimits)
    viewport_limits: PointerProperty(type=RPR_RenderLimits)

    # RENDER TILES
    use_tile_render: BoolProperty(
        name="Tiled rendering",
        description="Use tiles to do final rendering",
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

    # RAY DEPTH PROPERTIES
    use_clamp_radiance: BoolProperty(
        name="Clamp",
        description="Use clamp radiance",
        default=True,
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
        min=0.0, max=2.0,
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

    def init_rpr_context(self, rpr_context, is_final_engine=True, use_gl_interop=False):
        """ Initializes rpr_context by device settings """

        scene = self.id_data
        log("Syncing scene: %s" % scene.name)

        devices = self.get_devices(is_final_engine)

        context_flags = 0
        # enable CMJ sampler for adaptive sampling
        context_props = [pyrpr.CONTEXT_SAMPLER_TYPE, pyrpr.CONTEXT_SAMPLER_TYPE_CMJ]
        if devices.cpu_state:
            context_flags |= pyrpr.Context.cpu_device['flag']
            context_props.extend([pyrpr.CONTEXT_CPU_THREAD_LIMIT, devices.cpu_threads])

        metal_enabled = False
        if hasattr(devices, 'gpu_states'):
            for i, gpu_state in enumerate(devices.gpu_states):
                if gpu_state:
                    context_flags |= pyrpr.Context.gpu_devices[i]['flag']
                    if use_gl_interop:
                        context_flags |= pyrpr.CREATION_FLAGS_ENABLE_GL_INTEROP
                
                    if not metal_enabled and platform.system() == 'Darwin':
                        # only enable metal once and if a GPU is turned on
                        metal_enabled = True
                        context_flags |= pyrpr.CREATION_FLAGS_ENABLE_METAL
                        
        context_props.append(0) # should be followed by 0

        if self.trace_dump:
            if not os.path.isdir(self.trace_dump_folder):
                os.mkdir(self.trace_dump_folder)

            pyrpr.Context.set_parameter(None, 'tracingfolder', self.trace_dump_folder)
            pyrpr.Context.set_parameter(None, 'tracing', True)
        else:
            pyrpr.Context.set_parameter(None, 'tracing', False)

        rpr_context.init(context_flags, context_props)

        if metal_enabled:
            mac_vers_major = platform.mac_ver()[0].split('.')[1]
            # if this is mojave turn on MPS
            if float(mac_vers_major) >= 14:
                rpr_context.set_parameter("metalperformanceshader", 1)


    def get_devices(self, is_final_engine=True):
        """ Get render devices settings for current mode """
        devices_settings = get_user_settings()
        if is_final_engine or not devices_settings.separate_viewport_devices:
            return devices_settings.final_devices
        return devices_settings.viewport_devices

    def export_ray_depth(self, rpr_context):
        """ Exports ray depth settings """

        res = False

        res |= rpr_context.set_parameter('maxRecursion', self.max_ray_depth)
        res |= rpr_context.set_parameter('maxdepth.diffuse', self.diffuse_depth)
        res |= rpr_context.set_parameter('maxdepth.glossy', self.glossy_depth)
        res |= rpr_context.set_parameter('maxdepth.shadow', self.shadow_depth)
        res |= rpr_context.set_parameter('maxdepth.refraction', self.refraction_depth)
        res |= rpr_context.set_parameter('maxdepth.refraction.glossy', self.glossy_refraction_depth)
        res |= rpr_context.set_parameter('radianceclamp', self.clamp_radiance if self.use_clamp_radiance else sys.float_info.max)

        res |= rpr_context.set_parameter('raycastepsilon', self.ray_cast_epsilon * 0.001) # Convert millimeters to meters

        return res

    def export_render_mode(self, rpr_context):
        return rpr_context.set_parameter('rendermode', getattr(pyrpr, 'RENDER_MODE_' + self.render_mode))

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
