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
import math

import bpy
from . import object, material
from rprblender.utils import BLENDER_VERSION, get_prop_array_data, is_zero
from rprblender.engine.context import RPRContext2

from rprblender.utils import logging
log = logging.Log(tag='export.volume')


def key(obj: bpy.types.Object, smoke_modifier):
    return (object.key(obj), smoke_modifier.name)


def get_transform(obj: bpy.types.Object):
    # Set volume transform. Note: it should be scaled by 2.0
    transform = object.get_transform(obj)
    scale = np.identity(4, dtype=np.float32)
    scale[0, 0], scale[1, 1], scale[2, 2] = 2.0, 2.0, 2.0
    return transform @ scale


def get_smoke_modifier(obj: bpy.types.Object):
    if BLENDER_VERSION >= '2.82':
        return next((modifier for modifier in obj.modifiers
                     if modifier.type == 'FLUID' and modifier.fluid_type == 'DOMAIN'), None)
    else:
        return next((modifier for modifier in obj.modifiers
                     if modifier.type == 'SMOKE' and modifier.smoke_type == 'DOMAIN'), None)


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

    # getting smoke resolution and color_grid
    if BLENDER_VERSION >= '2.82':
        x, y, z = domain.domain_resolution
    else:
        amplify = domain.amplify if domain.use_high_resolution else 0
        x, y, z = ((amplify + 1) * i for i in domain.domain_resolution)

    if domain.use_noise:
        # smoke noise upscale the basic domain resolution
        x, y, z = (domain.noise_scale * e for e in (x, y, z))

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
