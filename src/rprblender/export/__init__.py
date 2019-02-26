import numpy as np
import bpy


class SyncError(RuntimeError):
    pass


def get_transform(obj):
    """ Returns transform matrix of blender object """

    if isinstance(obj, bpy.types.DepsgraphObjectInstance):
        if obj.is_instance:
            return np.array(obj.matrix_world, dtype=np.float32).reshape(4, 4)
        return np.array(obj.object.matrix_world, dtype=np.float32).reshape(4, 4)

    if isinstance(obj, bpy.types.Object):
        return np.array(obj.matrix_world, dtype=np.float32).reshape(4, 4)

    raise TypeError("Cannot get transform for object", obj)


def key(obj):
    """ Returns key of blender objects depending of its type """

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
        return (obj_key, obj.random_id)

    raise TypeError("Cannot create key for object", obj)


