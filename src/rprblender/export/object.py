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

from . import mesh, light, camera, to_mesh, volume, openvdb, particle, hair
from rprblender.utils import logging
log = logging.Log(tag='export.object')


def key(obj: bpy.types.Object):
    return f'{obj.name_full}_{obj.data.name_full}' if obj.type == 'MESH' and obj.is_from_instancer else obj.name_full


def get_transform(obj: bpy.types.Object):
    return np.array(obj.matrix_world, dtype=np.float32).reshape(4, 4)


def sync(rpr_context, obj: bpy.types.Object, **kwargs):
    """ sync the object and any data attached """

    from rprblender.engine.render_engine import RenderEngine

    log("sync", obj, obj.type)

    if obj.type == 'MESH':
        if obj.mode == 'OBJECT':
            # if in edit mode use to_mesh
            mesh.sync(rpr_context, obj, **kwargs)
        else:
            to_mesh.sync(rpr_context, obj, **kwargs)

    elif obj.type == 'LIGHT':
        light.sync(rpr_context, obj)

    elif obj.type == 'CAMERA':
        camera.sync(rpr_context, obj)

    elif obj.type in ('CURVE', 'FONT', 'SURFACE', 'META'):
        to_mesh.sync(rpr_context, obj, **kwargs)

    elif obj.type == 'VOLUME':
        openvdb.sync(rpr_context, obj, **kwargs)

    elif obj.type == 'CURVES':
        hair.sync_curves(rpr_context, obj)

    elif obj.type == 'EMPTY':
        pass

    else:
        log.warn("Object to sync not supported", obj, obj.type)

    if obj.type in ('MESH', 'CURVE', 'FONT', 'SURFACE', 'META'):
        volume.sync(rpr_context, obj)
        hair.sync(rpr_context, obj)

        # Note: particles should be exported separately in final render engine
        #       after motion blur, otherwise prev_location of particle will be (0, 0, 0)
        if rpr_context.engine_type != RenderEngine.TYPE:
            particle.sync(rpr_context, obj)


def sync_update(rpr_context, obj: bpy.types.Object, is_updated_geometry, is_updated_transform, **kwargs):
    """ Updates existing rpr object. Checks obj.type and calls corresponded sync_update() """

    log("sync_update", obj, is_updated_geometry, is_updated_transform)

    updated = False

    if obj.type == 'LIGHT':
        updated |= light.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform)

    elif obj.type == 'MESH':
        if obj.mode == 'OBJECT':
            updated |= mesh.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform, **kwargs)
        else:
            updated |= to_mesh.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform, **kwargs)
 
    elif obj.type in ('CURVE', 'FONT', 'SURFACE', 'META'):
        updated |= to_mesh.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform, **kwargs)

    elif obj.type == 'EMPTY':
        pass

    elif obj.type == 'VOLUME':
        updated |= openvdb.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform, **kwargs)

    elif obj.type == 'CURVES':
        updated |= hair.sync_update_curves(rpr_context, obj, is_updated_geometry, is_updated_transform)

    else:
        log.warn("Not supported object to sync_update", obj, obj.type)

    if obj.type in ('MESH', 'CURVE', 'FONT', 'SURFACE', 'META'):
        updated |= volume.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform)
        updated |= hair.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform)
        updated |= particle.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform)

    return updated


def cache_blur_data(rpr_context, obj: bpy.types.Object):
    if obj.type == 'MESH':
        if obj.mode == 'OBJECT':
            # if in edit mode use to_mesh
            mesh.cache_blur_data(rpr_context, obj)
        else:
            to_mesh.cache_blur_data(rpr_context, obj)

    elif obj.type == 'CAMERA':
        camera.cache_blur_data(rpr_context, obj)

    elif obj.type in ('CURVE', 'FONT', 'SURFACE', 'META'):
        to_mesh.cache_blur_data(rpr_context, obj)


def export_motion_blur(rpr_context, obj_key, transform):
    """Use the motion_blur_cache to set the transform motion"""
    next_transform = rpr_context.transform_cache.get(obj_key)
    if next_transform is None or np.all(transform == next_transform):
        return

    rpr_object = rpr_context.objects[obj_key]
    rpr_object.set_motion_transform(next_transform)
