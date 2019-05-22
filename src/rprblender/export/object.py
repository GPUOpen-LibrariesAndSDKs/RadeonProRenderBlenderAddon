import bpy
import numpy as np

from . import mesh, light, camera, particle, to_mesh, volume
from rprblender.utils import logging
log = logging.Log(tag='export.object')


def key(obj: bpy.types.Object):
    return obj.name


def get_transform(obj: bpy.types.Object):
    return np.array(obj.matrix_world, dtype=np.float32).reshape(4, 4)


def sync(rpr_context, obj: bpy.types.Object):
    """ sync the object and any data attached """

    log("sync", obj)

    if obj.type == 'MESH':
        mesh.sync(rpr_context, obj)

    elif obj.type == 'LIGHT':
        light.sync(rpr_context, obj)

    elif obj.type in ('CURVE', 'FONT', 'SURFACE', 'META'):
        to_mesh.sync(rpr_context, obj)

    else:
        log.warn("Object to sync not supported", obj, obj.type)

    volume.sync(rpr_context, obj)

def sync_update(rpr_context, obj: bpy.types.Object, is_updated_geometry, is_updated_transform):
    """ Updates existing rpr object. Checks obj.type and calls corresponded sync_update() """

    log("sync_update", obj, is_updated_geometry, is_updated_transform)

    if obj.type == 'LIGHT':
        return light.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform)

    if obj.type == 'MESH':
        return mesh.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform)

    if obj.type in ('CURVE', 'FONT', 'SURFACE', 'META'):
        return to_mesh.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform)

    if obj.type == 'EMPTY':
        return False

    log.warn("Not supported object to sync_update", obj, obj.type)

    return False
