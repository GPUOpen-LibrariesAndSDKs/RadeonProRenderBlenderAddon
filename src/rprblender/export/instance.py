import numpy as np
import bpy

from . import object
from rprblender.utils import logging
log = logging.Log(tag='export.instance')


def key(instance: bpy.types.DepsgraphObjectInstance):
    return (object.key(instance.parent), instance.random_id)


def get_transform(instance: bpy.types.DepsgraphObjectInstance):
    return np.array(instance.matrix_world, dtype=np.float32).reshape(4, 4)


def sync(rpr_context, instance: bpy.types.DepsgraphObjectInstance, motion_blur_info=None):
    """ sync the blender instance """

    assert instance.is_instance  # expecting: instance.is_instance == True

    instance_key = key(instance)
    log("sync", instance, instance_key)

    obj = instance.object

    if obj.type == 'MESH':
        obj_key = object.key(obj)
        rpr_mesh = rpr_context.objects.get(obj_key, None)
        if not rpr_mesh:
            # Instance of this object exists, but object itself isn't visible on the scene.
            # In this case we do additional object export and set visibility to False
            object.sync(rpr_context, obj, motion_blur_info)
            rpr_mesh = rpr_context.objects[obj_key]
            rpr_mesh.set_visibility(False)

        rpr_shape = rpr_context.create_instance(instance_key, rpr_mesh)
        rpr_shape.set_name(str(instance_key))
        rpr_shape.set_transform(get_transform(instance))

        # exporting visibility from parent object
        instance.parent.rpr.export_visibility(rpr_shape)

        rpr_context.scene.attach(rpr_shape)

    else:
        # TODO: Implement instances for other object types: lights, etc
        log.warn("Instance to sync not supported", instance, obj, obj.type)
