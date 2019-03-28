import bpy
from dataclasses import dataclass
import mathutils
import multiprocessing
from pathlib import Path

import rprblender


def is_rpr_active(context: bpy.types.Context):
    return context.scene.render.engine == 'RPR'


def package_root_dir():
    return Path(rprblender.__file__).parent


def get_cpu_threads_number():
    return multiprocessing.cpu_count()


@dataclass(eq=False)
class MotionBlurInfo:
    linear_velocity: tuple = (0.0, 0.0, 0.0)
    angular_momentum: tuple = (0.0, 0.0, 0.0, 0.0)
    momentum_scale: tuple = (1.0, 0.0, 0.0)

    def __init__(self, previous_frame, current_frame):
        """Calculate object velocities for two frames from corresponding world matrices"""
        mul_diff = previous_frame @ current_frame.inverted()
        transform_quat = mul_diff.to_quaternion()

        scale_vec = mul_diff.to_scale()

        velocity = (previous_frame - current_frame).to_translation()

        momentum_axis = transform_quat.axis
        momentum_angle = transform_quat.angle
        momentum_scale = (scale_vec - mathutils.Vector((1, 1, 1)))
        if momentum_axis.length < 0.5:
            momentum_axis.x, momentum_axis.y, momentum_axis.z, momentum_angle = 1.0, 0.0, 0.0, 0.0

        self.linear_velocity = (velocity.x, velocity.y, velocity.z)
        self.angular_momentum = (momentum_axis.x, momentum_axis.y, momentum_axis.z, momentum_angle)
        self.momentum_scale = (momentum_scale.x, momentum_scale.y, momentum_scale.z)
