from dataclasses import dataclass
import numpy as np

import bpy
import mathutils

from . import image
from rprblender.engine.context import RPRContext

from rprblender.utils import logging
log = logging.Log(tag='export.world')


IBL_LIGHT_NAME = "RPR.ENVIRONMENT.IBL.LIGHT"


@dataclass(init=False, eq=True, repr=True)
class WorldData:
    """ Comparable dataclass which holds all environment settings """

    enabled: bool = None
    mode: str = None
    gizmo_rotation: tuple = None
    ibl_type: str = None
    ibl_image: str = None
    ibl_color: tuple = None
    ibl_intensity: float = None

    def __init__(self, world: bpy.types.World):
        """ Returns WorldData from bpy.types.World """

        rpr = world.rpr
        self.enabled = rpr.enabled
        self.mode = rpr.light_type

        self.ibl_type = rpr.ibl_type
        self.ibl_intensity = rpr.ibl_intensity
        self.ibl_color = tuple(rpr.ibl_color)
        if rpr.ibl_image:
            self.ibl_image = rpr.ibl_image.name

        self.gizmo_rotation = tuple(rpr.gizmo_rotation)


def calculate_rotation_matrix(gizmo_rotation):
    """ Calculates rotation matrix from gizmo rotation """

    rotation_gizmo = (gizmo_rotation[0], gizmo_rotation[1], gizmo_rotation[2] - np.pi / 2.0)
    euler = mathutils.Euler(rotation_gizmo)
    rotation_matrix = np.array(euler.to_matrix(), dtype=np.float32)
    fixup = np.array([[1, 0, 0],
                      [0, 0, 1],
                      [0, 1, 1]], dtype=np.float32)
    matrix = np.identity(4, dtype=np.float32)
    matrix[:3, :3] = np.dot(fixup, rotation_matrix)

    return matrix


def sync(rpr_context: RPRContext, world: bpy.types.World):
    """ Creates pyrpr.EnvironmentLight from bpy.types.World """

    rpr = world.rpr
    if not rpr.enabled:
        return

    if rpr.light_type == 'SUN_SKY':
        # TODO: Implement sun and sky
        return

    # single rotation gizmo is used by IBL and environment overrides
    if rpr.gizmo:
        rpr.update_gizmo(None)
    matrix = calculate_rotation_matrix(rpr.gizmo_rotation)

    rpr_light = rpr_context.create_light(IBL_LIGHT_NAME, 'environment')
    rpr_light.set_group_id(0)

    if rpr.ibl_type == 'COLOR':
        rpr_light.set_color(*rpr.ibl_color)
    else:
        if rpr.ibl_image:
            rpr_light.set_image(image.sync(rpr_context, rpr.ibl_image))
        else:
            rpr_light.set_color(1.0, 0.0, 1.0)

    rpr_light.set_intensity_scale(rpr.ibl_intensity)
    rpr_light.set_transform(matrix, False)

    # TODO As soon as portal light type ready support it here

    rpr_context.scene.attach(rpr_light)


def sync_update(rpr_context: RPRContext, world: bpy.types.World, old_settings: WorldData, new_settings: WorldData):
    """ Update existing environment light from bpy.types.World or create a new light """

    rpr = world.rpr
    if old_settings.enabled != new_settings.enabled:
        if rpr.enabled:
            sync(rpr_context, world)
        else:
            rpr_context.remove_object(IBL_LIGHT_NAME)

        return True

    ret = False
    rpr_light = rpr_context.objects[IBL_LIGHT_NAME]

    if old_settings.ibl_color != new_settings.ibl_color or \
            old_settings.ibl_image != new_settings.ibl_image or \
            old_settings.ibl_type != new_settings.ibl_type:

        if rpr.ibl_type == 'COLOR':
            rpr_light.set_color(*rpr.ibl_color)
        else:
            if rpr.ibl_image:
                rpr_light.set_image(image.sync(rpr_context, rpr.ibl_image))
            else:
                rpr_light.set_color(1.0, 0.0, 1.0)

        ret = True

    if old_settings.ibl_intensity != new_settings.ibl_intensity:
        rpr_light.set_intensity_scale(rpr.ibl_intensity)
        ret = True

    if old_settings.gizmo_rotation != new_settings.gizmo_rotation:
        if rpr.gizmo:
            rpr.update_gizmo(None)
        matrix = calculate_rotation_matrix(rpr.gizmo_rotation)
        rpr_light.set_transform(matrix, False)
        ret = True

    return ret
