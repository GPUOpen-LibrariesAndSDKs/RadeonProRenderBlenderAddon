import bpy
import numpy as np

from . import mesh, light, camera, particle, to_mesh, volume
from rprblender.utils import logging
log = logging.Log(tag='export.object')


def key(obj: bpy.types.Object):
    return obj.name


def get_transform(obj: bpy.types.Object):
    return np.array(obj.matrix_world, dtype=np.float32).reshape(4, 4)


def sync(rpr_context, obj: bpy.types.Object, **kwargs):
    """ sync the object and any data attached """

    log("sync", obj, obj.type)

    if obj.type == 'MESH':
        mesh.sync(rpr_context, obj, **kwargs)

    elif obj.type == 'LIGHT':
        light.sync(rpr_context, obj)

    elif obj.type == 'CAMERA':
        camera.sync(rpr_context, obj)

    elif obj.type in ('CURVE', 'FONT', 'SURFACE', 'META'):
        to_mesh.sync(rpr_context, obj, **kwargs)

    elif obj.type == 'EMPTY':
        pass

    else:
        log.warn("Object to sync not supported", obj, obj.type)

    volume.sync(rpr_context, obj)


def sync_update(rpr_context, obj: bpy.types.Object, is_updated_geometry, is_updated_transform, **kwargs):
    """ Updates existing rpr object. Checks obj.type and calls corresponded sync_update() """

    log("sync_update", obj, is_updated_geometry, is_updated_transform)

    updated = False

    if obj.type == 'LIGHT':
        updated |= light.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform)

    elif obj.type == 'MESH':
        updated |= mesh.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform, **kwargs)

    elif obj.type in ('CURVE', 'FONT', 'SURFACE', 'META'):
        updated |= to_mesh.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform, **kwargs)

    elif obj.type == 'EMPTY':
        pass

    else:
        log.warn("Not supported object to sync_update", obj, obj.type)

    updated |= volume.sync_update(rpr_context, obj)

    return updated
