import bpy
from dataclasses import dataclass
import mathutils
import multiprocessing
import numpy as np
from pathlib import Path

import rprblender


def is_rpr_active(context: bpy.types.Context):
    return context.scene.render.engine == 'RPR'


def get_transform(obj):
    if isinstance(obj, bpy.types.DepsgraphObjectInstance):
        if obj.is_instance:
            return np.array(obj.matrix_world, dtype=np.float32).reshape(4, 4)
        return np.array(obj.object.matrix_world, dtype=np.float32).reshape(4, 4)

    if isinstance(obj, bpy.types.Object):
        return np.array(obj.matrix_world, dtype=np.float32).reshape(4, 4)

    raise TypeError("Cannot get transform for object", obj)


def key(obj):
    if isinstance(obj, bpy.types.Object):
        return obj.name
    if isinstance(obj, bpy.types.Mesh):
        return obj.name
    if isinstance(obj, bpy.types.Material):
        return obj.name
    if isinstance(obj, bpy.types.Node):
        return obj.name
    if isinstance(obj, bpy.types.Image):
        return obj.name
    if isinstance(obj, bpy.types.DepsgraphObjectInstance):
        obj_key = key(obj.object)
        if not obj.is_instance:
            return obj_key
        return obj_key + '-' + str(obj.random_id)

    raise TypeError("Cannot create key for object", obj)


def package_root_dir():
    return Path(rprblender.__file__).parent


def get_cpu_threads_number():
    return multiprocessing.cpu_count()


def get_tiles(width, height, n, m):
    for i in range(n):
        for j in range(m):
            yield (width * i // n, width * (i + 1) // n - 1,
                   height * j // n, height * (i + 1) // n - 1)


@dataclass(eq=False)
class MotionBlurInfo:
    linear_velocity: tuple = (0.0, 0.0, 0.0)
    angular_momentum: tuple = (0.0, 0.0, 0.0, 0.0)
    momentum_scale: tuple = (1.0, 0.0, 0.0)

    def __init__(self, previous_frame, current_frame, scale):
        """Calculate object velocities for two frames from corresponding world matrices"""
        mul_diff = previous_frame @ current_frame.inverted()
        transform_quat = mul_diff.to_quaternion()

        scale_vec = mul_diff.to_scale()

        translation = (previous_frame - current_frame).to_translation()

        velocity = translation * scale
        momentum_axis = transform_quat.axis
        momentum_angle = transform_quat.angle * scale
        momentum_scale = (scale_vec - mathutils.Vector((1, 1, 1))) * scale
        if momentum_axis.length < 0.5:
            momentum_axis.x, momentum_axis.y, momentum_axis.z, momentum_angle = 1.0, 0.0, 0.0, 0.0

        self.linear_velocity = (velocity.x, velocity.y, velocity.z)
        self.angular_momentum = (momentum_axis.x, momentum_axis.y, momentum_axis.z, momentum_angle)
        self.momentum_scale = (momentum_scale.x, momentum_scale.y, momentum_scale.z)
