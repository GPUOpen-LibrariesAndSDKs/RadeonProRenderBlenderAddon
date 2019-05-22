import numpy as np
import math

import bpy
from . import object, material

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


def sync(rpr_context, obj: bpy.types.Object):
    """ sync any volume attached to the object.  
        Note that volumes don't currently use motion blur """

    # find the smoke modifier
    smoke_modifier = next((modifier for modifier in obj.modifiers
                           if modifier.type == 'SMOKE' and modifier.smoke_type == 'DOMAIN'), None)
    if not smoke_modifier:
        return

    log("sync", smoke_modifier, obj)

    domain = smoke_modifier.domain_settings
    if len(domain.color_grid) == 0:
        # empty smoke.  warn and return 
        log.warn("Empty smoke domain", domain, smoke_modifier, obj)
        return

    # getting volume material
    volume_material = None
    if len(obj.material_slots) and obj.material_slots[0].material:
        volume_material = material.sync(rpr_context, obj.material_slots[0].material, 'Volume')

    if not isinstance(volume_material, dict):
        log.warn("not correct volume material", obj)
        return

    # creating rpr_volume
    volume_key = key(obj, smoke_modifier)
    rpr_volume = rpr_context.create_hetero_volume(volume_key)
    rpr_volume.set_name(str(volume_key))

    # getting smoke resolution and color_grid
    amplify = domain.amplify if domain.use_high_resolution else 0
    x, y, z = ((amplify + 1) * i for i in domain.domain_resolution)

    color_grid = np.fromiter(domain.color_grid, dtype=np.float32).reshape(x, y, z, 4)

    # set albedo grid
    albedo_grid = np.average(color_grid[:, :, :, :3], axis=3)
    color = volume_material['color'][:3]
    albedo_lookup = np.array([0.0, 0.0, 0.0, *color],
                             dtype=np.float32).reshape(-1, 3)
    rpr_volume.set_albedo_grid(np.ascontiguousarray(albedo_grid), albedo_lookup)

    # set density grid
    density_grid = color_grid[:, :, :, 3]
    density = volume_material['density']
    density_lookup = np.array([0.0, 0.0, 0.0, density, density, density],
                              dtype=np.float32).reshape(-1, 3)
    rpr_volume.set_density_grid(np.ascontiguousarray(density_grid), density_lookup)

    if not math.isclose(volume_material['emission'], 0.0):
        # set emission grid
        emission_color = np.array(volume_material['emission_color'][:3]) * volume_material['emission']
        emission_grid = np.fromiter(domain.flame_grid, dtype=np.float32).reshape(x, y, z)
        emission_lookup = np.array([0.0, 0.0, 0.0, *emission_color],
                                   dtype=np.float32).reshape(-1, 3)
        rpr_volume.set_emission_grid(emission_grid, emission_lookup)

    # set volume transform
    rpr_volume.set_transform(get_transform(obj))

    # attaching to scene and shape
    rpr_context.scene.attach(rpr_volume)
    rpr_obj = rpr_context.objects[object.key(obj)]
    rpr_obj.set_hetero_volume(rpr_volume)
