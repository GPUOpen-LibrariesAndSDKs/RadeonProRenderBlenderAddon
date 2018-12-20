import sys

import bpy
import pyrpr
from bpy.props import (
    BoolProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    BoolVectorProperty,
)

from rprblender import utils
from rprblender.utils import logging
from . import RPR_Properties


def log(*args):
    logging.info(*args, tag='Render')


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


class RPR_RenderProperties(RPR_Properties):
    devices: PointerProperty(type=RPR_RenderDevicesProperties)
    light_paths: PointerProperty(type=RPR_LightPathsProperties)
    sampling: PointerProperty(type=RPR_SamplingProperties)

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
