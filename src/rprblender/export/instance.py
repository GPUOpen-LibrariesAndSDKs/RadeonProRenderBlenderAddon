#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
import numpy as np
import bpy

from . import object, light, mesh, hair
from rprblender.engine.context import RPRContext
from rprblender.utils import logging
log = logging.Log(tag='export.instance')


def key(instance: bpy.types.DepsgraphObjectInstance):
    return (object.key(instance.parent), instance.random_id)


def get_transform(instance: bpy.types.DepsgraphObjectInstance):
    return np.array(instance.matrix_world, dtype=np.float32).reshape(4, 4)


def sync(rpr_context, instance: bpy.types.DepsgraphObjectInstance, **kwargs):
    """ sync the blender instance """

    assert instance.is_instance  # expecting: instance.is_instance == True

    instance_key = key(instance)
    log("sync", instance, instance_key)

    obj = instance.object

    if obj.type in ('MESH', 'CURVE', 'FONT', 'SURFACE', 'META'):
        obj_key = object.key(obj)
        rpr_mesh = rpr_context.objects.get(obj_key, None)
        if not rpr_mesh:
            # Instance of this object exists, but object itself isn't visible on the scene.
            # In this case we do additional object export and set visibility to False
            object.sync(rpr_context, obj, **kwargs)
            rpr_mesh = rpr_context.objects.get(obj_key, None)
            if not rpr_mesh:
                return
            rpr_mesh.set_visibility(False)

        rpr_shape = rpr_context.create_instance(instance_key, rpr_mesh)
        rpr_shape.set_name(str(instance_key))

        transform = get_transform(instance)
        rpr_shape.set_transform(transform)
        object.export_motion_blur(rpr_context, instance_key, transform)

        # exporting visibility from source object
        indirect_only = kwargs.get("indirect_only", False)
        mesh.export_visibility(instance.object, rpr_shape, indirect_only)

        rpr_context.scene.attach(rpr_shape)

        hair.sync(rpr_context, instance)

    elif obj.type == 'LIGHT':
        light.sync(rpr_context, obj, instance_key)
        rpr_light = rpr_context.objects[instance_key]
        rpr_light.set_name(str(instance_key))
        rpr_light.set_transform(get_transform(instance))

    else:
        raise ValueError("Unsupported object type for instance", instance, obj, obj.type)


def sync_update(rpr_context: RPRContext, instance: bpy.types.DepsgraphObjectInstance, is_updated_geometry, is_updated_transform, **kwargs):
    """ Update existing instance or create a new instance """
    log("sync_update", instance)

    inst_key = key(instance)
    rpr_shape = rpr_context.objects.get(inst_key, None)
    if not rpr_shape:
        sync(rpr_context, instance, **kwargs)
        return True

    if is_updated_geometry:
        rpr_context.remove_object(inst_key)
        sync(rpr_context, instance)
        return True

    if is_updated_transform:
        rpr_shape.set_transform(object.get_transform(instance))

    return True


def cache_blur_data(rpr_context, inst: bpy.types.DepsgraphObjectInstance):
    if inst.parent.rpr.motion_blur:
        rpr_context.transform_cache[key(inst)] = get_transform(inst)
