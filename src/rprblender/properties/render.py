import sys

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
from rprblender.utils import logging
from . import RPR_Properties


log = logging.Log(tag='Render')


class RPR_RenderLimits(bpy.types.PropertyGroup):
    ''' Properties for render limits: iteration limit or time limit'''

    type: EnumProperty(
        name="Iterations Limit",
        description="When to stop rendering a frame",
        items=(
            ('ITERATIONS', "Iterations", "Number of iterations"),
            ('TIME', "Time", "Time limit")
        ),
        default='ITERATIONS'
    )
    iterations: IntProperty(
        name="Iterations",
        description="Number of iterations to render for each pixel",
        min=1, default=50,
    )
    update_samples: IntProperty(
        name="Samples per View Update",
        description="The more samples, the less viewport updates for shorter render times",
        min=1, default=1,
    )
    seconds: IntProperty(
        name="Seconds",
        description="Limit rendering process in seconds",
        min=1, default=10
    )
    thumbnail_iterations: IntProperty(
        name="Thumbnail Iterations",
        description="Material and light previews number of iterations to render for each pixel",
        min=1, default=50,
    )


# Getting list of available devices for RPR_RenderDevices
enum_devices = [('CPU', "CPU", "Use CPU for rendering"),]
if len(pyrpr.Context.gpu_devices) > 0:
    enum_devices.insert(0, ('GPU', "GPU", "Use GPU device for rendering"))
    enum_devices.append(('GPU+CPU', "GPU+CPU", "Use GPU+CPU devices for rendering"))


class RPR_RenderDevices(bpy.types.PropertyGroup):
    ''' Properties for render devices: CPU, GPUs '''

    def update_states(self, context):
        if len(pyrpr.Context.gpu_devices) > 0:
            # selecting first gpu if no gpu and cpu is selected
            if not any(self.gpu_states) and not self.cpu_state:
                self.gpu_states[0] = True
        else:
            # if no GPU then cpu always should be enabled
            self.cpu_state = True

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
        default=utils.get_cpu_threads_number()
    )


class RPR_RenderProperties(RPR_Properties):
    ''' Main render properties. Available from scene.rpr '''

    saved_addon_version: bpy.props.IntVectorProperty(
        name="Version"
    )

    # RENDER DEVICES
    devices: PointerProperty(type=RPR_RenderDevices)
    viewport_devices: PointerProperty(type=RPR_RenderDevices)
    separate_viewport_devices: BoolProperty(
        name="Separate Viewport Devices",
        description="Use separate viewport and preview render devices configuration",
        default=False,
    )

    # RENDER LIMITS
    limits: PointerProperty(type=RPR_RenderLimits)
    viewport_limits: PointerProperty(type=RPR_RenderLimits)

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

    # Motion Blur
    def update_motion_blur_exposure(self, context):
        selected = []
        if self.motion_blur_exposure_apply == 'ACTIVE':
            if context.scene and context.scene.camera:
                selected = [context.scene.camera]
        elif self.motion_blur_exposure_apply == 'SELECTED':
            selected = context.selected_editable_objects
        else:
            selected = context.editable_objects

        for obj in selected:
            if obj.type != 'CAMERA':
                continue
            obj.rpr.motion_blur = True
            obj.rpr.motion_blur_exposure = self.motion_blur_exposure

    def update_motion_blur_scale(self, context):
        if self.motion_blur_scale_apply == 'SELECTED':
            selected = context.selected_editable_objects
        else:
            selected = context.editable_objects

        for obj in selected:
            if obj.type not in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META', 'LIGHT'):
                continue
            if obj.type == 'LIGHT' and obj.data.type != 'AREA':
                continue
            obj.rpr.motion_blur = True
            obj.rpr.motion_blur_scale = self.motion_blur_scale

    motion_blur: bpy.props.BoolProperty(
        name="Motion Blur", description="Enable Motion Blur",
        default=False,
    )

    motion_blur_exposure_apply: bpy.props.EnumProperty(
        name="Apply exposure",
        items=(('ACTIVE', "Active Camera", "Active Camera on scene"),
               ('SELECTED', "Selected Camera(s)", "Selected Camera(s) (self explanatory)"),
               ('ALL', "Entire scene", "Entire scene (autoselects all cameras)")),
        description="Apply exposure to camera(s)",
        default='ACTIVE',
    )

    motion_blur_exposure: bpy.props.FloatProperty(
        name="Exposure", description="Motion Blur Exposure for camera(s)",
        min=0.0,
        default=1.0,
        update=update_motion_blur_exposure
    )

    motion_blur_scale_apply: bpy.props.EnumProperty(
        name="Apply scale",
        items=(('SELECTED', "Selected Object(s)", "Selected Object(s) (self explanatory)"),
               ('ALL', "Entire scene", "Entire scene (autoselects all objects)")),
        description="Apply scale to object(s)",
        default='SELECTED'
    )

    motion_blur_scale: bpy.props.FloatProperty(
        name="Scale", description="Motion Blur Scale for object(s)",
        min=0.0,
        default=1.0,
        update=update_motion_blur_scale
    )


    def sync(self, rpr_context, is_final_engine=True, use_gl_interop=False):
        scene = self.id_data
        log("Syncing scene: %s" % scene.name)

        devices = self.devices if is_final_engine or not self.separate_viewport_devices else \
                  self.viewport_devices

        context_flags = 0
        context_props = []
        if devices.cpu_state:
            context_flags |= pyrpr.Context.cpu_device['flag']
            context_props.extend([pyrpr.CONTEXT_CREATEPROP_CPU_THREAD_LIMIT, devices.cpu_threads])
        if hasattr(devices, 'gpu_states'):
            for i, gpu_state in enumerate(devices.gpu_states):
                if gpu_state:
                    context_flags |= pyrpr.Context.gpu_devices[i]['flag']
                    if use_gl_interop:
                        context_flags |= pyrpr.CREATION_FLAGS_ENABLE_GL_INTEROP

        if platform.system() == 'Darwin':
            context_flags |= pyrpr.CREATION_FLAGS_ENABLE_METAL
            mac_vers_major = platform.mac_ver()[0].split('.')[1]
            # if this is mojave turn on MPS
            if float(mac_vers_major) >= 14:
                context_props.extend([pyrpr.CONTEXT_METAL_PERFORMANCE_SHADER, 1])

        context_props.append(0) # should be followed by 0
        rpr_context.init(context_flags, context_props)

        self.set_ray_depth(rpr_context)

    def sync_update(self, rpr_context):
        return self.set_ray_depth(rpr_context)

    def set_ray_depth(self, rpr_context):
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
