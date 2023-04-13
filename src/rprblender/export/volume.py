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

from . import object, material
from rprblender.utils import BLENDER_VERSION, get_prop_array_data, is_zero
from rprblender.engine.context import RPRContext2
from rprblender.utils import helper_lib

from rprblender.utils import logging
log = logging.Log(tag='export.volume')


def key(obj: bpy.types.Object, smoke_modifier):
    return (object.key(obj), smoke_modifier.name)


def get_transform(obj: bpy.types.Object):
    transform = object.get_transform(obj)
    scale = np.identity(4, dtype=np.float32)
    scale[0, 0], scale[1, 1], scale[2, 2] = (abs(obj.dimensions[i] / obj.scale[i]) if obj.scale[i] != 0 else 0.0
                                             for i in range(3))
    return transform @ scale


def get_smoke_modifier(obj: bpy.types.Object):
    if BLENDER_VERSION >= '2.82':
        return next((modifier for modifier in obj.modifiers
                     if modifier.type == 'FLUID' and modifier.fluid_type == 'DOMAIN'
                     and modifier.domain_settings.domain_type == 'GAS'), None)
    else:
        return next((modifier for modifier in obj.modifiers
                     if modifier.type == 'SMOKE' and modifier.smoke_type == 'DOMAIN'), None)


def get_domain_resolution(domain, grid_name):
    if BLENDER_VERSION >= '2.82':
        x, y, z = domain.domain_resolution
    else:
        amplify = domain.amplify if domain.use_high_resolution else 0
        x, y, z = ((amplify + 1) * i for i in domain.domain_resolution)

    if domain.use_noise and grid_name not in ('velocity', 'heat'):
        # smoke noise upscale the basic domain resolution
        x, y, z = (domain.noise_scale * e for e in (x, y, z))

    return x, y, z


def create_grid_sampler_node(rpr_context, obj, grid_name, default_grid_name):

    grid = None
    smoke_modifier = get_smoke_modifier(obj)
    grid_name = grid_name.lower()

    if smoke_modifier:
        domain = smoke_modifier.domain_settings
        if len(domain.density_grid) == 0:
            return None

        data = None
        if grid_name == 'color':
            data = get_prop_array_data(domain.color_grid).reshape(*get_domain_resolution(domain, grid_name), -1)
            data = np.average(data[:, :, :, :3], axis=3)
        elif grid_name == 'velocity':
            data = get_prop_array_data(domain.velocity_grid).reshape(*get_domain_resolution(domain, grid_name), -1)
            data = np.average(data[:, :, :, :3], axis=3)
        elif grid_name == 'density':
            data = get_prop_array_data(domain.density_grid).reshape(*get_domain_resolution(domain, grid_name))
        elif grid_name == 'flame':
            data = get_prop_array_data(domain.flame_grid).reshape(*get_domain_resolution(domain, grid_name))
        elif grid_name == 'heat':
            data = get_prop_array_data(domain.heat_grid).reshape(*get_domain_resolution(domain, grid_name))
        elif grid_name == 'temperature':
            data = get_prop_array_data(domain.temperature_grid).reshape(*get_domain_resolution(domain, grid_name))
        elif default_grid_name:
            return create_grid_sampler_node(rpr_context, obj, default_grid_name, None)

        if is_zero(data):
            return None

        grid = rpr_context.create_grid_from_3d_array(data)

    elif obj.type == 'VOLUME':
        if not obj.data.grids.is_loaded:
            obj.data.grids.load()

        vdb_file = obj.data.grids.frame_filepath
        if not vdb_file:  # nothing to export
            return None

        if BLENDER_VERSION >= '3.5':
            obj.data.grids.unload()

            import pyopenvdb as vdb

            grids = vdb.readAllGridMetadata(vdb_file)
            try:
                grid = next((vdb.read(vdb_file, g.name) for g in grids if g.name == grid_name), None)

            except Exception as err:
                raise RuntimeError(err)

            if grid is None:
                return None

            # TODO: add support for float vector grid
            if grid.valueTypeName != 'float':
                return

            size = grid.evalLeafDim()
            values = np.zeros(shape=size, dtype=np.float32)

            # ijk - specifies the index coordinates of the voxel to be copied to array index
            # otherwise grid becomes shifted
            grid.copyToArray(values, ijk=grid.evalLeafBoundingBox()[0])
            indices = np.nonzero(values)

            data = {
                'size': size,
                'values': values[indices],
                'indices': np.ascontiguousarray(np.transpose(indices).astype('uint32')),
            }

        else:
            if not helper_lib.is_openvdb_support:
                obj.data.grids.unload()
                return None

            grids = helper_lib.vdb_read_grids_list(vdb_file)
            if grid_name not in grids:
                obj.data.grids.unload()
                return None

            # TODO: add support for float vector grid
            if obj.data.grids[grid_name].channels != 1:
                obj.data.grids.unload()
                return None

            obj.data.grids.unload()

            data = helper_lib.vdb_read_grid_data(vdb_file, grid_name)

        grid = rpr_context.create_grid_from_array_indices(*data['size'], data['values'], data['indices'])

    if not grid:
        return None

    node = rpr_context.create_material_node(pyrpr.MATERIAL_NODE_GRID_SAMPLER)
    node.set_input(pyrpr.MATERIAL_INPUT_DATA, grid)
    return node


def sync(rpr_context, obj: bpy.types.Object):
    """ sync any volume attached to the object.  
        Note that volumes don't currently use motion blur """

    # find the smoke modifier
    smoke_modifier = get_smoke_modifier(obj)
    if not smoke_modifier or isinstance(rpr_context, RPRContext2):
        return

    log("sync", smoke_modifier, obj)

    domain = smoke_modifier.domain_settings
    if len(domain.color_grid) == 0:
        # empty smoke.  warn and return 
        log.warn("Empty smoke domain", domain, smoke_modifier, obj)
        return

    # getting volume material
    volume_material = None
    if obj.material_slots and obj.material_slots[0].material:
        volume_material = material.sync(rpr_context, obj.material_slots[0].material, 'Volume')

    if not volume_material:
        log.warn("No volume material for smoke domain", obj)
        return

    data = volume_material.data

    # creating rpr_volume
    volume_key = key(obj, smoke_modifier)
    rpr_volume = rpr_context.create_hetero_volume(volume_key)
    rpr_volume.set_name(str(volume_key))

    x, y, z = get_domain_resolution(domain)

    color_grid = get_prop_array_data(domain.color_grid).reshape(x, y, z, -1)

    # set albedo grid
    albedo_data = np.average(color_grid[:, :, :, :3], axis=3)
    albedo_grid = rpr_context.create_grid_from_3d_array(np.ascontiguousarray(albedo_data))
    color = data['color']
    albedo_lookup = np.array([0.0, 0.0, 0.0, *color],
                             dtype=np.float32).reshape(-1, 3)
    rpr_volume.set_grid('albedo', albedo_grid)
    rpr_volume.set_lookup('albedo', albedo_lookup)

    # set density grid
    density_data = get_prop_array_data(domain.density_grid).reshape(x, y, z)
    density_grid = rpr_context.create_grid_from_3d_array(np.ascontiguousarray(density_data))
    density = data['density']
    density_lookup = np.array([0.0, 0.0, 0.0, density, density, density],
                              dtype=np.float32).reshape(-1, 3)
    rpr_volume.set_grid('density', density_grid)
    rpr_volume.set_lookup('density', density_lookup)

    emission_color = data['emission_color']
    if not is_zero(emission_color):
        # set emission grid
        emission_data = get_prop_array_data(domain.flame_grid).reshape(x, y, z)
        emission_grid = rpr_context.create_grid_from_3d_array(np.ascontiguousarray(emission_data))
        emission_lookup = np.array([0.0, 0.0, 0.0, *emission_color],
                                   dtype=np.float32).reshape(-1, 3)
        rpr_volume.set_grid('emission', emission_grid)
        rpr_volume.set_lookup('emission', emission_lookup)

    # set volume transform
    rpr_volume.set_transform(get_transform(obj))

    # attaching to scene and shape
    rpr_context.scene.attach(rpr_volume)
    rpr_obj = rpr_context.objects[object.key(obj)]
    rpr_obj.set_hetero_volume(rpr_volume)


def sync_update(rpr_context, obj: bpy.types.Object, is_updated_geometry, is_updated_transform):
    obj_key = object.key(obj)

    updated = False

    if rpr_context.has_volumes(obj_key):
        rpr_context.remove_volumes(obj_key)
        updated = True

    sync(rpr_context, obj)

    if rpr_context.has_volumes(obj_key):
        updated = True

    return updated
