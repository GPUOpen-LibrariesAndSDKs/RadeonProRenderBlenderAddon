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

import pyrpr
from rprblender.utils import helper_lib, BLENDER_VERSION
from rprblender.engine.context import RPRContext2

from . import object, material, volume

from rprblender.utils import logging
log = logging.Log(tag='export.openvdb')


def get_transform(obj: bpy.types.Object):
    # creating bound transform matrix
    min_xyz = tuple(min(b[i] for b in obj.bound_box) for i in range(3))
    max_xyz = tuple(max(b[i] for b in obj.bound_box) for i in range(3))
    d = tuple(max_xyz[i] - min_xyz[i] for i in range(3))
    c = tuple((max_xyz[i] + min_xyz[i]) / 2 for i in range(3))

    bound_mat = np.array((d[0], 0, 0, c[0],
                          0, d[1], 0, c[1],
                          0, 0, d[2], c[2],
                          0, 0, 0, 1), dtype=np.float32).reshape(4, 4)

    # result is: object matrix * bound matrix
    return object.get_transform(obj) @ bound_mat


def sync(rpr_context, obj: bpy.types.Object, **kwargs):
    if not isinstance(rpr_context, RPRContext2):
        return

    if not (helper_lib.is_openvdb_support or BLENDER_VERSION >= '3.5'):
        log.warn("OpenVDB is not supported")
        return

    volume_node = get_volume_material(rpr_context, obj)
    if not volume_node:  # nothing to export
        return

    # creating volume
    obj_key = object.key(obj)
    rpr_mesh = rpr_context.create_mesh(
            obj_key,
            None, None, None,
            None, None, None,
            None,
            {pyrpr.MESH_VOLUME_FLAG: 1}
        )
    rpr_mesh.set_name(str(obj_key))
    rpr_mesh.set_volume_material(volume_node)
    rpr_mesh.set_transform(get_transform(obj))
    rpr_context.scene.attach(rpr_mesh)


def sync_update(rpr_context, obj: bpy.types.Object, is_updated_geometry, is_updated_transform, **kwargs):
    if not (helper_lib.is_openvdb_support or BLENDER_VERSION >= '3.5'):
        return False

    obj_key = object.key(obj)

    rpr_mesh = rpr_context.objects.get(obj_key, None)

    if not rpr_mesh:
        # no such mesh with volume => creating mesh with volume
        sync(rpr_context, obj, **kwargs)
        return True

    if is_updated_geometry:
        # mesh exists, but its settings were changed => recreating mesh with volume
        rpr_context.remove_object(obj_key)
        sync(rpr_context, obj, **kwargs)
        return True

    if is_updated_transform:
        # updating only mesh and volume transform
        transform = get_transform(obj)
        rpr_mesh.set_transform(transform)

    volume_node = get_volume_material(rpr_context, obj)
    rpr_mesh.set_volume_material(volume_node)

    return True


def get_volume_material(rpr_context, obj):
    if obj.material_slots and obj.material_slots[0].material:
        volume_node = material.sync(rpr_context, obj.material_slots[0].material, 'Volume', obj=obj)
        if volume_node:
            return volume_node

    density_grid_node = volume.create_grid_sampler_node(rpr_context, obj, 'density', None)
    if not density_grid_node:
        return None

    d = obj.data.display.density
    volume_node = rpr_context.create_material_node(pyrpr.MATERIAL_NODE_VOLUME)
    volume_node.set_input(pyrpr.MATERIAL_INPUT_DENSITY, d * 5)
    volume_node.set_input(pyrpr.MATERIAL_INPUT_G, 0.0)
    volume_node.set_input(pyrpr.MATERIAL_INPUT_MULTISCATTER, True)
    volume_node.set_input(pyrpr.MATERIAL_INPUT_COLOR, (0.7, 0.7, 0.7))
    volume_node.set_input(pyrpr.MATERIAL_INPUT_DENSITYGRID, density_grid_node)

    return volume_node
