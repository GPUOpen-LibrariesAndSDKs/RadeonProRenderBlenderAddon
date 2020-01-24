"""
This module exports following blender object types: 'CURVE', 'FONT', 'SURFACE', 'META'.
It converts such blender object into blender mesh and exports it as mesh.
"""

import bpy

from . import object, mesh

from rprblender.utils import logging
log = logging.Log(tag='export.to_mesh')


def sync(rpr_context, obj: bpy.types.Object, **kwargs):
    """ Converts object into blender's mesh and exports it as mesh """

    try:
        # This operation adds new mesh into bpy.data.meshes, that's why it should be removed after usage.
        # obj.to_mesh() could also return None for META objects.
        new_mesh = obj.to_mesh()
        log("sync", obj, new_mesh)

        if new_mesh:
            mesh.sync(rpr_context, obj, mesh=new_mesh, **kwargs)
            return True

        return False

    finally:
        # it's important to clear created mesh
        obj.to_mesh_clear()


def sync_update(rpr_context, obj: bpy.types.Object, is_updated_geometry, is_updated_transform, **kwargs):
    """ Updates existing rpr mesh or creates a new mesh """

    log("sync_update", obj)

    obj_key = object.key(obj)
    rpr_shape = rpr_context.objects.get(obj_key, None)
    if not rpr_shape:
        sync(rpr_context, obj, **kwargs)
        return True

    if is_updated_geometry:
        rpr_context.remove_object(obj_key)
        sync(rpr_context, obj)
        return True

    if is_updated_transform:
        rpr_shape.set_transform(object.get_transform(obj))
        return True

    material_override = kwargs.get('material_override', None)
    return mesh.assign_materials(rpr_context, rpr_shape, obj, material_override=material_override)
