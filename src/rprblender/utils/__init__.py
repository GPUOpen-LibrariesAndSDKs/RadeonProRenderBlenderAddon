import numpy as np
from pathlib import Path

import bpy
import rprblender


def is_rpr_active(context: bpy.types.Context):
    return context.scene.render.engine == 'RPR'


def get_transform(obj):
    return np.array(obj.matrix_world, dtype=np.float32).reshape(4, 4)


def key(obj):
    return obj.name


def package_root_dir():
    return Path(rprblender.__file__).parent


def get_cpu_threads_number():
    # TODO: This should be implemented
    return 16