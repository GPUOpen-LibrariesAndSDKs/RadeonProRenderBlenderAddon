from dataclasses import dataclass
import numpy as np

import bpy
import mathutils
import pyrpr

from . import image
from rprblender.engine.context import RPRContext

from rprblender.utils import logging
log = logging.Log(tag='export.world')


IBL_LIGHT_NAME = "RPR.ENVIRONMENT.IBL.LIGHT"
BACKGROUND_OVERRIDE_NAME = 'RPR.ENVIRONMENT.BACKGROUND'
REFLECTION_OVERRIDE_NAME = 'RPR.ENVIRONMENT.REFLECTION'
REFRACTION_OVERRIDE_NAME = 'RPR.ENVIRONMENT.REFRACTION'
TRANSPARENCY_OVERRIDE_NAME = 'RPR.ENVIRONMENT.TRANSPARENCY'

WARNING_IMAGE_NOT_DEFINED_COLOR = (1.0, 0.0, 1.0)

# "ignore these environment lights" for scene update in viewport_engine
ENVIRONMENT_LIGHTS_NAMES = (
    IBL_LIGHT_NAME,
    BACKGROUND_OVERRIDE_NAME,
    REFLECTION_OVERRIDE_NAME,
    REFRACTION_OVERRIDE_NAME,
    TRANSPARENCY_OVERRIDE_NAME
)


@dataclass(init=False, eq=True, repr=True)
class WorldData:
    """ Comparable dataclass which holds all environment settings """

    @dataclass(eq=True, repr=True)
    class OverrideData:
        """ Store and compare single Environment Override category settings """
        enabled: bool = None
        data_type: str = None
        color_data: tuple = None
        image_data: str = None

    enabled: bool = None
    mode: str = None
    gizmo_rotation: tuple = None
    ibl_type: str = None
    ibl_image: str = None
    ibl_color: tuple = None
    ibl_intensity: float = None

    background: OverrideData = None
    reflection: OverrideData = None
    refraction: OverrideData = None
    transparency: OverrideData = None

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

        self.background = WorldData.OverrideData(rpr.override_background, rpr.background_type,
                                                 rpr.background_color, rpr.background_image)
        self.reflection = WorldData.OverrideData(rpr.override_reflection, rpr.reflection_type,
                                                 rpr.reflection_color, rpr.reflection_image)
        self.refraction = WorldData.OverrideData(rpr.override_refraction, rpr.refraction_type,
                                                 rpr.refraction_color, rpr.refraction_image)
        self.transparency = WorldData.OverrideData(rpr.override_transparency, rpr.transparency_type,
                                                   rpr.transparency_color, rpr.transparency_image)


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

    def create_environment_light(key: str, data_type: str, color_data: tuple, image_data: bpy.types.Image):
        """
        Create environment light using color/image data by data_type
        :rtype: pyrpr.EnvironmentLight
        """
        env_light = rpr_context.create_light(key, 'environment')
        env_light.set_intensity_scale(rpr.ibl_intensity)  # same intensity used for all environment elements

        if data_type == 'COLOR':
            env_light.set_color(*color_data)
        else:
            if image_data:
                try:
                    rpr_image = image.sync(rpr_context, image_data)
                except ValueError as e:
                    log.warn(e)
                    env_light.set_color(*WARNING_IMAGE_NOT_DEFINED_COLOR)
                else:
                    env_light.set_image(rpr_image)
            else:
                env_light.set_color(*WARNING_IMAGE_NOT_DEFINED_COLOR)

        env_light.set_transform(matrix, False)
        env_light.set_group_id(0)

        return env_light

    log("sync", world)

    rpr = world.rpr
    if not rpr.enabled:
        return

    # single rotation gizmo is used for IBL and environment overrides
    if rpr.gizmo:
        rpr.update_gizmo(None)
    matrix = calculate_rotation_matrix(rpr.gizmo_rotation)

    # Main IBL light
    if rpr.light_type == 'IBL':
        light = create_environment_light(IBL_LIGHT_NAME, rpr.ibl_type, rpr.ibl_color, rpr.ibl_image)
        rpr_context.scene.attach(light)
    # TODO: Implement "Sun and Sky" IBL

    # Environment overrides
    if rpr.override_background:
        light = create_environment_light(BACKGROUND_OVERRIDE_NAME, rpr.background_type,
                                         rpr.background_color, rpr.background_image)
        rpr_context.scene.add_environment_override(pyrpr.SCENE_ENVIRONMENT_OVERRIDE_BACKGROUND, light)

    if rpr.override_reflection:
        light = create_environment_light('RPR.ENVIRONMENT.REFLECTION', rpr.reflection_type,
                                         rpr.reflection_color, rpr.reflection_image)
        rpr_context.scene.add_environment_override(pyrpr.SCENE_ENVIRONMENT_OVERRIDE_REFLECTION, light)

    if rpr.override_refraction:
        light = create_environment_light(REFRACTION_OVERRIDE_NAME, rpr.refraction_type,
                                         rpr.refraction_color, rpr.refraction_image)
        rpr_context.scene.add_environment_override(pyrpr.SCENE_ENVIRONMENT_OVERRIDE_REFRACTION, light)

    if rpr.override_transparency:
        light = create_environment_light('RPR.ENVIRONMENT.TRANSPARENCY', rpr.transparency_type,
                                         rpr.transparency_color, rpr.transparency_image)
        rpr_context.scene.add_environment_override(pyrpr.SCENE_ENVIRONMENT_OVERRIDE_TRANSPARENCY, light)


def sync_update(rpr_context: RPRContext, world: bpy.types.World, old_settings: WorldData, new_settings: WorldData):
    """ Update existing environment light from bpy.types.World or create a new light """

    def update_light(light: pyrpr.EnvironmentLight, data_type: str, color_data: tuple, image_data: bpy.types.Image):
        """ Update core environment light colors to color/image data by data_type """
        if data_type == 'COLOR':
            light.set_color(*color_data)
        else:
            if image_data:
                try:
                    rpr_image = image.sync(rpr_context, image_data)
                except ValueError as e:
                    log.warn(e)
                    light.set_color(*WARNING_IMAGE_NOT_DEFINED_COLOR)
                else:
                    light.set_image(rpr_image)
            else:
                light.set_color(*WARNING_IMAGE_NOT_DEFINED_COLOR)

    def create_override(key: str, data_type: str, color_data: tuple, image_data: bpy.types.Image):
        """
        Create environment light to use as environment override, set colors data, intensity and transform
        :rtype: pyrpr.EnvironmentLight
        """
        env_light = rpr_context.create_light(key, 'environment')
        update_light(env_light, data_type, color_data, image_data)
        env_light.set_group_id(0)
        env_light.set_intensity_scale(rpr.ibl_intensity)
        env_light.set_transform(matrix, False)
        return env_light

    log("sync_update", world)

    # environment lightning enabled/disabled
    rpr = world.rpr
    if old_settings.enabled != new_settings.enabled:
        if rpr.enabled:
            sync(rpr_context, world)
        else:
            rpr_context.remove_object(IBL_LIGHT_NAME)

        return True

    ret = False

    if rpr.gizmo:
        rpr.update_gizmo(None)
    matrix = calculate_rotation_matrix(rpr.gizmo_rotation)

    ibl_light = rpr_context.objects[IBL_LIGHT_NAME]
    background = rpr_context.objects.get(BACKGROUND_OVERRIDE_NAME, None)
    reflection = rpr_context.objects.get(REFLECTION_OVERRIDE_NAME, None)
    refraction = rpr_context.objects.get(REFRACTION_OVERRIDE_NAME, None)
    transparency = rpr_context.objects.get(TRANSPARENCY_OVERRIDE_NAME, None)

    # IBL color/image changed
    if old_settings.ibl_color != new_settings.ibl_color or \
            old_settings.ibl_image != new_settings.ibl_image or \
            old_settings.ibl_type != new_settings.ibl_type:

        update_light(ibl_light, rpr.ibl_type, rpr.ibl_color, rpr.ibl_image)

        ret = True

    # Background override enabler/disabled
    if old_settings.background.enabled != new_settings.background.enabled:
        if rpr.override_background:
            background = create_override(BACKGROUND_OVERRIDE_NAME, rpr.background_type,
                                         rpr.background_color, rpr.background_image)
            rpr_context.scene.add_environment_override(pyrpr.SCENE_ENVIRONMENT_OVERRIDE_BACKGROUND, background)
        else:
            rpr_context.scene.remove_environment_override(pyrpr.SCENE_ENVIRONMENT_OVERRIDE_BACKGROUND)
            background = None
        ret = True
    elif background and old_settings.background != new_settings.background:
        # Background color/image changed
        update_light(background, rpr.background_type, rpr.background_color, rpr.background_image)
        ret = True

    # Reflection override enabler/disabled
    if old_settings.reflection.enabled != new_settings.reflection.enabled:
        if rpr.override_reflection:
            reflection = create_override(REFLECTION_OVERRIDE_NAME, rpr.reflection_type,
                                         rpr.reflection_color, rpr.reflection_image)
            rpr_context.scene.add_environment_override(pyrpr.SCENE_ENVIRONMENT_OVERRIDE_REFLECTION, reflection)
        else:
            rpr_context.scene.remove_environment_override(pyrpr.SCENE_ENVIRONMENT_OVERRIDE_REFLECTION)
            reflection = None
        ret = True
    elif reflection and old_settings.reflection != new_settings.reflection:
        # Reflection color/image changed
        update_light(reflection, rpr.reflection_type, rpr.reflection_color, rpr.reflection_image)
        ret = True

    # Refraction override enabler/disabled
    if old_settings.refraction.enabled != new_settings.refraction.enabled:
        if rpr.override_refraction:
            refraction = create_override(REFRACTION_OVERRIDE_NAME, rpr.refraction_type,
                                         rpr.refraction_color, rpr.refraction_image)
            rpr_context.scene.add_environment_override(pyrpr.SCENE_ENVIRONMENT_OVERRIDE_REFRACTION, refraction)
        else:
            rpr_context.scene.remove_environment_override(pyrpr.SCENE_ENVIRONMENT_OVERRIDE_REFRACTION)
            refraction = None
        ret = True
    elif refraction and old_settings.refraction != new_settings.refraction:
        # Refraction color/image changed
        update_light(refraction, rpr.refraction_type, rpr.refraction_color, rpr.refraction_image)
        ret = True

    # Transparency override enabler/disabled
    if old_settings.transparency.enabled != new_settings.transparency.enabled:
        if rpr.override_transparency:
            transparency = create_override(TRANSPARENCY_OVERRIDE_NAME, rpr.transparency_type,
                                           rpr.transparency_color, rpr.transparency_image)
            rpr_context.scene.add_environment_override(pyrpr.SCENE_ENVIRONMENT_OVERRIDE_TRANSPARENCY, transparency)
        else:
            rpr_context.scene.remove_environment_override(pyrpr.SCENE_ENVIRONMENT_OVERRIDE_TRANSPARENCY)
            transparency = None
        ret = True
    elif transparency and old_settings.transparency != new_settings.transparency:
        # Transparency color/image changed
        update_light(transparency, rpr.transparency_type, rpr.transparency_color, rpr.transparency_image)
        ret = True

    # Intensity changed
    if old_settings.ibl_intensity != new_settings.ibl_intensity:
        ibl_light.set_intensity_scale(rpr.ibl_intensity)
        if background:
            background.set_intensity_scale(rpr.ibl_intensity)
        if reflection:
            reflection.set_intensity_scale(rpr.ibl_intensity)
        if refraction:
            refraction.set_intensity_scale(rpr.ibl_intensity)
        if transparency:
            transparency.set_intensity_scale(rpr.ibl_intensity)
        ret = True

    # Rotation changed
    if old_settings.gizmo_rotation != new_settings.gizmo_rotation:
        ibl_light.set_transform(matrix, False)
        if background:
            background.set_transform(matrix, False)
        if reflection:
            reflection.set_transform(matrix, False)
        if refraction:
            refraction.set_transform(matrix, False)
        if transparency:
            transparency.set_transform(matrix, False)
        ret = True

    return ret
