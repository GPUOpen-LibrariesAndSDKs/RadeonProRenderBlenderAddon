import bpy
from dataclasses import dataclass
import mathutils
import numpy as np


from . import logging
from .image import create_flat_color_image_data, get_rpr_image


log = logging.Log(tag='world')


IBL_LIGHT_NAME = "RPR.ENVIRONMENT.IBL.LIGHT"


@dataclass(init=False, eq=True, repr=True)
class WorldData:
    enabled: bool = None
    mode: str = None
    gizmo_rotation: tuple = None
    ibl_type: str = None
    ibl_image: str = None
    ibl_color: tuple = None
    ibl_intensity: float = None


def get_world_data(world: bpy.types.World):
    result = WorldData()

    # dump current world settings
    rpr = world.rpr
    result.enabled = bool(rpr.enabled)
    result.mode = str(rpr.light_type)

    result.ibl_type = str(rpr.ibl_type)
    result.ibl_intensity = float(rpr.ibl_intensity)
    result.ibl_color = tuple(rpr.ibl_color)
    if rpr.ibl_image:
        result.ibl_image = str(rpr.ibl_image.name)

    result.gizmo_rotation = tuple(rpr.gizmo_rotation)

    return result


def calculate_rotation_matrix(gizmo_rotation):
    rotation_gizmo = (gizmo_rotation[0], gizmo_rotation[1], gizmo_rotation[2] - np.pi / 2.0)
    euler = mathutils.Euler(rotation_gizmo)
    rotation_matrix = np.array(euler.to_matrix(), dtype=np.float32)
    fixup = np.array([[1, 0, 0],
                      [0, 0, 1],
                      [0, 1, 1]], dtype=np.float32)
    matrix = np.identity(4, dtype=np.float32)
    matrix[:3, :3] = np.dot(fixup, rotation_matrix)

    return matrix


def create_environment_image(rpr_context, env_type, env_color, env_image):
    """Create environment light image as well as environment override images"""
    image = None
    if env_type == 'COLOR':
        image = create_flat_color_image_data(rpr_context, IBL_LIGHT_NAME, env_color)
    elif env_image:
        try:
            image = get_rpr_image(rpr_context, IBL_LIGHT_NAME, env_image)
        except ValueError as e:
            log.error("Cant's read environment image: {}".format(e))

    if not image:  # Purple "ERROR" skies
        image = create_flat_color_image_data(rpr_context, IBL_LIGHT_NAME, (1, 0, 1, 1))
    return image
