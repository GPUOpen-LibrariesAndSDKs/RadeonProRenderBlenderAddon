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
)

from rprblender import utils
from rprblender.utils import logging
from . import RPR_Properties


log = logging.Log(tag='Render')


class RPR_RenderDevicesProperties(bpy.types.PropertyGroup):
    use_cpu: BoolProperty(
        name="CPU",
        description="Use CPU as rendering resource. Note: GPU only rendering may be faster unless you have a CPU with many cores",
        default=False
    )
    use_gpu: BoolProperty(
        name="GPU",
        description="Use GPU as rendering resource",
        default=True
    )
    cpu_threads: IntProperty(
        name="CPU Threads",
        description="Number of CPU threads for render, optimal value is about the number of physical CPU cores",
        min=1, max=utils.get_cpu_threads_number(),
        default=utils.get_cpu_threads_number()
    )
    gpu_states: BoolVectorProperty(
        name="",
        size=len(pyrpr.Context.gpu_devices),
        default=(i == 0 for i in range(len(pyrpr.Context.gpu_devices)))
    )


class RPR_SamplingProperties(bpy.types.PropertyGroup):
    iterations: IntProperty(
        name="Iterations",
        description="Limit the max number of rendering iterations",
        min=1, default=50,
    )
    iteration_samples: IntProperty(
        name="Samples per Iteration",
        description="Limit the max number of rendering iterations",
        min=1, default=1,
    )

class RPR_LightPathsProperties(bpy.types.PropertyGroup):
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
    max_diffuse_depth: IntProperty(
        name="Diffuse", description="Max diffuse ray depth",
        min=0, soft_min=2, soft_max=50,
        default=3,
    )
    max_glossy_depth: IntProperty(
        name="Glossy", description="Max glossy ray depth",
        min=0, soft_min=2, soft_max=50,
        default=5,
    )
    max_shadow_depth: IntProperty(
        name="Shadow", description="Max shadow depth",
        min=0, soft_min=2, soft_max=50,
        default=5,
    )
    max_refraction_depth: IntProperty(
        name="Refraction", description="Max refraction ray depth",
        min=0, soft_min=2, soft_max=50,
        default=5,
    )
    max_glossy_refraction_depth: IntProperty(
        name="Glossy Refraction", description="Max glossy refraction ray depth",
        min=0, soft_min=2, soft_max=50,
        default=5,
    )
    ray_epsilon: FloatProperty(
        name="Ray Epsilon (mm)", description="Ray cast epsilon (in millimeters)",
        min=0.0, max=2.0,
        default=0.02,
    )


class RPR_DenoiserProperties(RPR_Properties):
    enable: BoolProperty(
        description="Enable RPR Denoiser",
        default=False,
    )

    filter_type: EnumProperty(
        name="Filter Type",
        items=(
            ('bilateral', "Bilateral", "Bilateral", 0),
            ('lwr', "Local Weighted Regression", "Local Weighted Regression", 1),
            ('eaw', "Edge Avoiding Wavelets", "Edge Avoiding Wavelets", 2),
        ),
        description="Filter type",
        default='eaw'
    )

    scale_by_iterations: BoolProperty(
        name="Scale Denoising Iterations",
        description="Scale the amount of denoiser blur by number of iterations.  This will give more blur for renders with less samples, and become sharper as more samples are added.",
        default=True
    )

    # bilateral props
    radius: IntProperty(
        name="Radius",
        description="Radius",
        min = 1, max = 50, default = 1
    )
    p_sigma: FloatProperty(
        name="Position Sigma",
        description="Threshold for detecting position differences",
        min = 0.0, soft_max = 1.0, default = .1
    )

    # EAW props
    color_sigma: FloatProperty(
        name="Color Sigma",
        description="Threshold for detecting color differences",
        min = 0.0, soft_max = 1.0, default = .75
    )
    normal_sigma: FloatProperty(
        name="Normal Sigma",
        description="Threshold for detecting normal differences",
        min = 0.0, soft_max = 1.0, default = .01
    )
    depth_sigma: FloatProperty(
        name="Depth Sigma",
        description="Threshold for detecting z depth differences",
        min = 0.0, soft_max = 1.0, default = .01
    )
    trans_sigma: FloatProperty(
        name="ID Sigma",
        description="Threshold for detecting Object ID differences",
        min = 0.0, soft_max = 1.0, default = .01
    )

    # LWR props
    samples: IntProperty(
        name="Samples",
        description="Number of samples used, more will give better results while being longer",
        min = 2, soft_max = 10, max = 100, default = 4
    )
    half_window: IntProperty(
        name="Filter radius",
        description="The radius of pixels to sample from",
        min = 1, soft_max = 10, max = 100, default = 4
    )
    bandwidth: FloatProperty(
        name="Bandwidth",
        description="Bandwidth of the filter, a samller value gives less noise, but may filter image detail",
        min = 0.0, max = 1.0, default = .1
    )

    def sync(self, rpr_context):
        rpr_context.setup_image_filter({
            'enable': self.enable,
            'filter_type': self.filter_type,
            'color_sigma': self.color_sigma,
            'normal_sigma': self.normal_sigma,
            'p_sigma': self.p_sigma,
            'depth_sigma': self.depth_sigma,
            'trans_sigma': self.trans_sigma,
            'radius': self.radius,
            'samples': self.samples,
            'half_window': self.half_window,
            'bandwidth': self.bandwidth,
        })


class RPR_RenderProperties(RPR_Properties):
    devices: PointerProperty(type=RPR_RenderDevicesProperties)
    light_paths: PointerProperty(type=RPR_LightPathsProperties)
    sampling: PointerProperty(type=RPR_SamplingProperties)
    denoiser: PointerProperty(type=RPR_DenoiserProperties)

    def sync(self, rpr_context):
        scene = self.id_data
        log("Syncing scene: %s" % scene.name)

        context_flags = 0
        context_props = []
        if self.devices.use_cpu and pyrpr.Context.cpu_device:
            context_flags |= pyrpr.Context.cpu_device['flag']
            context_props.extend([pyrpr.CONTEXT_CREATEPROP_CPU_THREAD_LIMIT, self.devices.cpu_threads])
        if self.devices.use_gpu:
            for i, gpu_state in enumerate(self.devices.gpu_states):
                if gpu_state:
                    context_flags |= pyrpr.Context.gpu_devices[i]['flag']

        width = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
        height = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)

        context_props.append(0) # should be followed by 0
        rpr_context.init(width, height, context_flags, context_props)
        rpr_context.scene.set_name(scene.name)

        # TODO: setup other AOVs, image filters
        rpr_context.enable_aov(pyrpr.AOV_COLOR)

        # set light paths values
        rpr_context.set_parameter('maxRecursion', self.light_paths.max_ray_depth)
        rpr_context.set_parameter('maxdepth.diffuse', self.light_paths.max_diffuse_depth)
        rpr_context.set_parameter('maxdepth.glossy', self.light_paths.max_glossy_depth)
        rpr_context.set_parameter('maxdepth.shadow', self.light_paths.max_shadow_depth)
        rpr_context.set_parameter('maxdepth.refraction', self.light_paths.max_refraction_depth)
        rpr_context.set_parameter('maxdepth.refraction.glossy', self.light_paths.max_glossy_refraction_depth)
        rpr_context.set_parameter('radianceclamp', self.light_paths.clamp_radiance if self.light_paths.use_clamp_radiance else sys.float_info.max)

        rpr_context.set_parameter('raycastepsilon', self.light_paths.ray_epsilon * 0.001) # Convert millimeters to meters

        # set sampling values
        rpr_context.set_parameter('iterations', self.sampling.iteration_samples)
        rpr_context.set_max_iterations(self.sampling.iterations)

        scene.world.rpr.sync(rpr_context)

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
