import bpy

from . import mesh, light, camera, key
from rprblender.utils import logging
log = logging.Log(tag='export.object')


def sync_motion_blur(rpr_context, obj: bpy.types.Object, motion_blur_info):
    if motion_blur_info is None:
        return

    obj_key = key(obj)
    rpr_obj = rpr_context.objects[obj_key]

    rpr_obj.set_linear_motion(*motion_blur_info.linear_velocity)
    rpr_obj.set_angular_motion(*motion_blur_info.angular_momentum)
    rpr_obj.set_scale_motion(*motion_blur_info.momentum_scale)


def sync(rpr_context, obj: bpy.types.Object, obj_instance, motion_blur_info):
    """ sync the object and any data attached """

    log("Syncing object", obj)

    if obj.type == 'MESH':
        mesh.sync(rpr_context, obj_instance)
        sync_motion_blur(rpr_context, obj, motion_blur_info)
    elif obj.type == 'LIGHT':
        light.sync(rpr_context, obj)
        sync_motion_blur(rpr_context, obj, motion_blur_info)
    elif obj.type == 'CAMERA':
        camera.sync(rpr_context, obj)
        sync_motion_blur(rpr_context, obj, motion_blur_info)
    else:
        log.warn("Object to sync not supported", obj, obj.type)


def sync_update(rpr_context, obj: bpy.types.Object, is_updated_geometry, is_updated_transform):
    """ Updates existing rpr object. Checks obj.type and calls corresponded sync_update() """

    log("sync_update", obj, is_updated_geometry, is_updated_transform)

    if obj.type == 'LIGHT':
        return light.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform)

    if obj.type == 'MESH':
        return mesh.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform)

    log.warn("Not supported object to sync_update", obj)

    return False
