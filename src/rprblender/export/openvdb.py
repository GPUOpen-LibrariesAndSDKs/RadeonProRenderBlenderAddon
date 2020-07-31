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
import os

import numpy as np

import bpy

import pyrpr
from rprblender.utils import helper_lib, IS_WIN, IS_MAC, is_zero
from rprblender.utils import get_sequence_frame_file_path

from . import mesh, object, material

from rprblender.utils import logging
log = logging.Log(tag='export.openvdb')


def key(obj: bpy.types.Object):
    return (object.key(obj), 'openvdb')


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


def sequence_frame_number(scene_frame, mode, start, duration, offset):
    """ Get sequence frame number from sequence settings and current scene frame """
    frame = scene_frame - start + 1
    if mode == 'CLIP':
        if frame < 1 or frame > duration:
            return None

    elif mode == 'EXTEND':
        frame = min(max(frame, 1), duration)

    elif mode == 'REPEAT':
        frame %= duration
        if frame < 0:
            frame += duration
        if frame == 0:
            frame = duration

    else:  # mode == 'PING_PONG'
        pingpong_duration = duration * 2 - 2
        frame %= pingpong_duration
        if frame < 0:
            frame += pingpong_duration
        if frame == 0:
            frame = pingpong_duration
        if frame > duration:
            frame = duration * 2 - frame
    frame += offset

    return frame


def get_volume_file_path(volume, scene_frame):
    """ Get full file path for VDB grids data """
    source_path = bpy.path.abspath(volume.filepath)

    if not volume.is_sequence:  # use filename for non-sequence
        if not os.path.exists(source_path):
            log.warn(f"Unable to find OpenVDB file {source_path}")
            return None

        return source_path

    # get VDB frame number for current scene frame
    frame_duration = volume.frame_duration
    frame_start = volume.frame_start
    frame_offset = volume.frame_offset

    mode = volume.sequence_mode

    frame_number = sequence_frame_number(scene_frame, mode, frame_start, frame_duration, frame_offset)
    return get_sequence_frame_file_path(source_path, frame_number)


def sync(rpr_context, obj: bpy.types.Object, **kwargs):
    if not (IS_WIN or IS_MAC):
        return

    # getting openvdb grid data
    volume = obj.data
    obj_key = object.key(obj)

    vdb_file = get_volume_file_path(volume, kwargs['frame_current'])
    if not vdb_file:  # nothing to export
        return

    grids = helper_lib.vdb_read_grids_list(vdb_file)

    def get_rpr_grid(grid_name):
        if grid_name not in grids:
            return None

        data = helper_lib.vdb_read_grid_data(vdb_file, grid_name)

        values = data['values']
        m = values.max()
        if m > 1.0:
            values /= m

        return rpr_context.create_grid_from_array_indices(
            *data['size'], values, data['indices'])

    material_data = get_material_data(rpr_context, obj)

    density_grid = get_rpr_grid(material_data['density_attr'])
    if not density_grid:
        log.warn(f"No '{material_data['density_attr']}' grid in {vdb_file}.", obj)
        return

    # creating hetero volume
    volume_key = key(obj)
    rpr_volume = rpr_context.create_hetero_volume(volume_key)
    rpr_volume.set_name(str(volume_key))

    rpr_volume.set_grid('density', density_grid)
    rpr_volume.set_grid('albedo', density_grid)

    emission_color = material_data['emission_color']
    if not is_zero(emission_color):
        emission_grid = density_grid
        if material_data['temperature_attr'] != material_data['density_attr']:
            emission_grid = get_rpr_grid(material_data['temperature_attr'])
            if not emission_grid:
                log.warn(f"No '{material_data['temperature_attr']}' grid in {vdb_file} for "
                         f"emission, '{material_data['density_attr']}' grid will be used.", obj)
                emission_grid = density_grid

        rpr_volume.set_grid('emission', emission_grid)

    assign_material(rpr_volume, material_data)

    # creating bound box shape
    mesh_data = mesh.MeshData.init_from_shape_type('CUBE', 1.0, 1.0, 0)
    rpr_shape = rpr_context.create_mesh(
        obj_key,
        mesh_data.vertices, mesh_data.normals, mesh_data.uvs,
        mesh_data.vertex_indices, mesh_data.normal_indices, mesh_data.uv_indices,
        mesh_data.num_face_vertices
    )
    rpr_shape.set_name(obj.name)

    transform = get_transform(obj)
    rpr_shape.set_transform(transform)

    mat = rpr_context.create_material_node(pyrpr.MATERIAL_NODE_TRANSPARENT)
    mat.set_input(pyrpr.MATERIAL_INPUT_COLOR, (1.0, 1.0, 1.0))

    rpr_shape.set_material(mat)
    rpr_context.scene.attach(rpr_shape)

    # attaching rpr_volume to rpr_shape
    rpr_volume.set_transform(transform)

    rpr_context.scene.attach(rpr_volume)
    rpr_shape.set_hetero_volume(rpr_volume)


def sync_update(rpr_context, obj: bpy.types.Object, is_updated_geometry, is_updated_transform, **kwargs):
    if not (IS_WIN or IS_MAC):
        return

    obj_key = object.key(obj)

    rpr_mesh = rpr_context.objects.get(obj_key, None)

    if not rpr_mesh:
        # no such mesh with volume => creating mesh with volume
        sync(rpr_context, obj, **kwargs)
        return True

    material_data = get_material_data(rpr_context, obj)
    rpr_volume = rpr_context.volumes[key(obj)]

    emission_changed = ('emission' in rpr_volume.grids) == is_zero(material_data['emission_color'])
    if is_updated_geometry or emission_changed:
        # mesh exists, but its settings were changed => recreating mesh with volume
        rpr_context.remove_object(obj_key)
        sync(rpr_context, obj, **kwargs)
        return True

    if is_updated_transform:
        # updating only mesh and volume transform
        transform = get_transform(obj)
        rpr_mesh.set_transform(transform)

        rpr_volume.set_transform(transform)

    assign_material(rpr_volume, material_data)

    return True


def get_material_data(rpr_context, obj):
    if obj.material_slots and obj.material_slots[0].material:
        mat = material.sync(rpr_context, obj.material_slots[0].material, 'Volume')
        if mat:
            return mat.data

    d = obj.data.display.density
    return {
        'color': (d, d, d),
        'density': d,
        'density_attr': "density",
        'emission_color': (0.0, 0.0, 0.0),
        'temperature_attr': "temperature",
    }


def assign_material(rpr_volume, material_data):
    d = material_data['density']
    rpr_volume.set_lookup('density', np.array([0.0, 0.0, 0.0, d, d, d],
                                              dtype=np.float32).reshape(-1, 3))

    color = material_data['color']
    rpr_volume.set_lookup('albedo', np.array([0.0, 0.0, 0.0, *color],
                                             dtype=np.float32).reshape(-1, 3))

    emission_color = material_data['emission_color']
    if not is_zero(emission_color):
        rpr_volume.set_lookup('emission', np.array([0.0, 0.0, 0.0, *emission_color],
                                                 dtype=np.float32).reshape(-1, 3))
