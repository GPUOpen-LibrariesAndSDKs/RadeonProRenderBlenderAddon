import numpy as np
import bpy


def is_rpr_active(context: bpy.types.Context):
    return context.scene.render.engine == 'RPR'

def get_transform(obj):
    return np.array(obj.matrix_world, dtype=np.float32).reshape(4, 4)