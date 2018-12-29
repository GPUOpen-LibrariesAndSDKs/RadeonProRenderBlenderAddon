import numpy as np
from pathlib import Path
import multiprocessing

import bpy
import rprblender


def is_rpr_active(context: bpy.types.Context):
    return context.scene.render.engine == 'RPR'


def get_transform(obj_instance:bpy.types.DepsgraphObjectInstance):
    if obj_instance.is_instance:
        return np.array(obj_instance.matrix_world, dtype=np.float32).reshape(4, 4)
    return np.array(obj_instance.object.matrix_world, dtype=np.float32).reshape(4, 4)


def key(obj):
    if isinstance(obj, bpy.types.Object):
        return obj.name
    if isinstance(obj, bpy.types.Mesh):
        return obj.name
    if isinstance(obj, bpy.types.Material):
        return obj.name
    if isinstance(obj, bpy.types.Node):
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
