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

from rprblender import utils
from rprblender.utils import logging
from . import RPR_Properties


log = logging.Log(tag='Render')


class RPR_RenderLimits(bpy.types.PropertyGroup):
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
    iteration_samples: IntProperty(
        name="Samples per Iteration",
        description="Number of samples per each rendering iteration",
        min=1, default=1,
    )
    seconds: IntProperty(
        name="Seconds",
        description="Limit rendering process in seconds",
        min=1, default=10
    )


enum_devices = [('CPU', "CPU", "Use CPU for rendering"),]
if len(pyrpr.Context.gpu_devices) > 0:
    enum_devices.insert(0, ('GPU', "GPU", "Use GPU device for rendering"))
    enum_devices.append(('GPU+CPU', "GPU+CPU", "Use GPU+CPU devices for rendering"))


class RPR_RenderProperties(RPR_Properties):
    saved_addon_version: bpy.props.IntVectorProperty(
        name="Version"
    )

    # DEVICES
    devices: EnumProperty(
        name="Devices",
        description="Device to use for rendering",
        items=enum_devices,
        default=enum_devices[0][0]
    )
    cpu_threads: IntProperty(
        name="CPU Threads",
        description="Number of CPU threads for render, optimal value is about the number of physical CPU cores",
        min=1, max=utils.get_cpu_threads_number(),
        default=utils.get_cpu_threads_number()
    )

    def update_gpu_states(self, context):
        # selecting first gpu if no gpu is selected
        if not any(self.gpu_states):
            self.gpu_states[0] = True

    if len(pyrpr.Context.gpu_devices) > 0:
        gpu_states: BoolVectorProperty(
            name="",
            size=len(pyrpr.Context.gpu_devices),
            default=(True,) * len(pyrpr.Context.gpu_devices),
            update=update_gpu_states
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

    # RENDER LIMITS
    limits: PointerProperty(type=RPR_RenderLimits)
    viewport_limits: PointerProperty(type=RPR_RenderLimits)

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

    def sync(self, rpr_context, use_gl_interop=False):
        scene = self.id_data
        log("Syncing scene: %s" % scene.name)

        context_flags = 0
        context_props = []
        if self.devices in ['CPU', 'GPU+CPU']:
            context_flags |= pyrpr.Context.cpu_device['flag']
            context_props.extend([pyrpr.CONTEXT_CREATEPROP_CPU_THREAD_LIMIT, self.cpu_threads])
        if self.devices in ['GPU', 'GPU+CPU']:
            for i, gpu_state in enumerate(self.gpu_states):
                if gpu_state:
                    context_flags |= pyrpr.Context.gpu_devices[i]['flag']

            if use_gl_interop:
                context_flags |= pyrpr.CREATION_FLAGS_ENABLE_GL_INTEROP

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
