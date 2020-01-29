from dataclasses import dataclass, field
import math
from typing import Tuple

import numpy as np
import math

import bpy
import mathutils

import pyrpr
import pyhybrid

from . import image
from rprblender.engine.context import RPRContext
from rprblender.utils import helper_lib

from rprblender.utils import logging
log = logging.Log(tag='export.world')


WARNING_IMAGE_NOT_DEFINED_COLOR = (1.0, 0.0, 1.0)
STUDIO_LIGHT_DEFAULT_COLOR = (0.051, 0.051, 0.051)  # Blender's default background color in viewport


def set_light_image(rpr_context, rpr_light, image_name):
    image_obj = bpy.data.images[image_name]
    try:
        rpr_image = image.sync(rpr_context, image_obj)
    except ValueError as e:
        log.warn(e)
        rpr_light.set_color(*WARNING_IMAGE_NOT_DEFINED_COLOR)
    else:
        rpr_light.set_image(rpr_image)


def set_light_studio_image(rpr_context, rpr_light, studio_light):
    file_path = image.cache_image_file_path(studio_light)
    rpr_image = rpr_context.create_image_file(None, file_path)
    rpr_light.set_image(rpr_image)


def remove_environment_overrides(rpr_context):
    for core_id in tuple(rpr_context.scene.environment_overrides.keys()):
        rpr_context.scene.remove_environment_override(core_id)


def remove_environment_lights(rpr_context):
    remove_environment_overrides(rpr_context)

    if rpr_context.scene.environment_light:
        rpr_context.scene.remove_environment_light()


def set_light_rotation(rpr_light, rotation: Tuple[float]) -> np.array:
    """ Calculates rotation matrix from gizmo rotation """

    matrix = np.identity(4, dtype=np.float32)
    if isinstance(rpr_light, pyhybrid.Light):
        euler = mathutils.Euler((rotation[0], rotation[2] - np.pi/2, rotation[1]))
    else:
        euler = mathutils.Euler((rotation[0], rotation[1], rotation[2] - np.pi/2))

    rotation_matrix = np.array(euler.to_matrix(), dtype=np.float32)
    fixup = np.array([[1, 0, 0],
                      [0, 0, 1],
                      [0, 1, 0]], dtype=np.float32)

    matrix[:3, :3] = np.dot(fixup, rotation_matrix)
    rpr_light.set_transform(matrix, False)
    return matrix


@dataclass(init=True, eq=False)
class RenderRegion:
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0

    def is_empty(self):
        return self.x2 <= self.x1 and self.y2 <= self.y1


@dataclass(init=False, eq=True)
class Backplate:
    """
    Environment backplate class is a handler of flat background image.
    Used as an alternative to the 360 degrees IBL-kind Background Override.

    Stores source image pixels cropped to render size as numpy array
    Exports
    """

    enabled: bool = False
    name: str = None

    source_pixels: image.ImagePixels = field(default=None, repr=False)
    source_size: Tuple[int, int, int, int] = field(default=None, repr=True)

    def __init__(self, world_data, render_size):
        self.enabled = bool(world_data.background_image)
        if not world_data.background_image:
            return

        self.name = world_data.background_image.name

        self.source_pixels, self.source_size = self.get_cropped_image(
            world_data.background_image, render_size
        )

    @staticmethod
    def calculate_cropped_size(x1: int, y1: int, x2: int, y2: int) -> tuple:
        """ Calculate cropped source region size to fit target region aspect ratio """
        ratio_image = x1 / y1
        ratio_render = x2 / y2

        # close ratios - no cropping required
        if math.isclose(ratio_image, ratio_render):
            return x1, y1

        # crop horizontal size
        if ratio_image > ratio_render:
            return y1 * x2 / y2, y1

        # crop vertical size
        return x1, x1 * y2 / x2

    @staticmethod
    def calculate_cropped_region(size_x, size_y, target_x, target_y) -> tuple:
        """ Get region coordinates for cropped image size """
        x1 = 0
        y1 = 0
        x2 = size_x - 1
        y2 = size_y - 1

        if size_x > target_x:
            half_size = size_x / 2
            half_target = target_x / 2
            x1 = half_size - half_target
            x2 = half_size + half_target
        elif size_y > target_y:
            half_size = size_y / 2
            half_target = target_y / 2
            y1 = half_size - half_target
            y2 = half_size + half_target

        x1 = max(0, int(x1))
        y1 = max(0, int(y1))
        x2 = min(size_x, int(x2))
        y2 = min(size_y, int(y2))

        return x1, y1, x2, y2

    def get_cropped_image(self, texture: bpy.types.Image, render_size: Tuple[int]) \
            -> Tuple[image.ImagePixels, tuple]:
        """ Crop source image to render size aspect ration, store pixels and result size """
        # crop source image size to fit target aspect ratio
        size = self.calculate_cropped_size(
            texture.size[0], texture.size[1],
            render_size[0], render_size[1],
        )

        # get pixels region for cropped size
        region = self.calculate_cropped_region(texture.size[0], texture.size[1], size[0], size[1])

        # extract pixels region from source image
        pixels = image.ImagePixels(texture, region)

        return pixels, pixels.size

    def export(self, rpr_context):
        rpr_image = None
        if self.enabled and self.name:
            texture = bpy.data.images[self.name]
            try:
                rpr_image = image.sync_image_region(
                    rpr_context, texture,
                    0, 0,
                    texture.size[0]-1, texture.size[1]-1,
                    flipud=False
                )
            except ValueError as e:
                log.warn(e)

        rpr_context.scene.set_background_image(rpr_image)

    def export_full(self, rpr_context):
        if not self.source_size:
            return

        rpr_image = self.source_pixels.export_full(rpr_context)
        rpr_context.scene.set_background_image(rpr_image)

    def export_tile(self, rpr_context, x1: float, y1: float, x2: float, y2: float):
        if not self.source_size:
            return

        # convert float tile coordinate to int pixel coordinates
        region = (
            int(x1 * self.source_size[0]), int(y1 * self.source_size[1]),
            int(x2 * self.source_size[0]), int(y2 * self.source_size[1]),
        )

        rpr_image = self.source_pixels.export_region(rpr_context, *region)
        rpr_context.scene.set_background_image(rpr_image)


@dataclass(init=False, eq=True, repr=True)
class WorldData:
    """ Comparable dataclass which holds all environment settings """

    @dataclass(init=False, eq=True)
    class OverrideData:
        """ Store and compare single Environment Override category settings """
        color: tuple = None
        image: str = None
        image_type: str = 'SPHERE'
        studio_light: str = None
        intensity: float = 1.0

    @dataclass(eq=True)
    class IblData:
        image: str = None
        studio_light: str = None
        color: tuple = None

        @staticmethod
        def init_from_ibl(ibl):
            data = WorldData.IblData()
            if ibl.image:
                data.image = ibl.image.name
            else:
                data.color = tuple(ibl.color)

            return data

        @staticmethod
        def init_from_shading(shading):
            data = WorldData.IblData()
            data.studio_light = shading.studio_light
            return data

        def export(self, rpr_context, rotation):
            rpr_light = rpr_context.scene.environment_light
            if not rpr_light:
                rpr_light = rpr_context.create_environment_light()
                rpr_context.scene.add_environment_light(rpr_light)

            if self.image:
                set_light_image(rpr_context, rpr_light, self.image)
            elif self.studio_light:
                set_light_studio_image(rpr_context, rpr_light, self.studio_light)
            else:
                rpr_light.set_color(*self.color)

            set_light_rotation(rpr_light, rotation)

    @dataclass(init=False, eq=True)
    class SunSkyData:
        resolution: int

        azimuth: float
        altitude: float

        turbidity: float
        sun_glow: float
        sun_disc: float
        saturation: float
        horizon_height: float
        horizon_blur: float
        filter_color: tuple
        ground_color: tuple

        def __init__(self, sun_sky):
            self.resolution = int(sun_sky.resolution)

            self.azimuth = sun_sky.azimuth
            self.altitude = sun_sky.altitude

            self.turbidity = sun_sky.turbidity
            self.sun_glow = sun_sky.sun_glow
            self.sun_disc = sun_sky.sun_disc
            self.saturation = sun_sky.saturation
            self.horizon_height = sun_sky.horizon_height
            self.horizon_blur = sun_sky.horizon_blur
            self.filter_color = tuple(sun_sky.filter_color)
            self.ground_color = tuple(sun_sky.ground_color)

        def export(self, rpr_context, rotation):
            remove_environment_overrides(rpr_context)

            rpr_light = rpr_context.scene.environment_light
            if not rpr_light:
                rpr_light = rpr_context.create_environment_light()
                rpr_context.scene.add_environment_light(rpr_light)

            helper_lib.set_sun_horizontal_coordinate(self.azimuth, self.altitude)
            helper_lib.set_sky_params(
                self.turbidity, self.sun_glow, self.sun_disc,
                self.horizon_height, self.horizon_blur, self.saturation,
                self.filter_color, self.ground_color
            )

            im = helper_lib.generate_sky_image(self.resolution, self.resolution)
            rpr_image = rpr_context.create_image_data(None, im)

            rpr_light.set_image(rpr_image)
            set_light_rotation(rpr_light, (rotation[0], rotation[1], rotation[2] + self.azimuth))

    intensity: float = 0.0
    ibl: IblData = None
    sun_sky: SunSkyData = None
    overrides: {str: OverrideData} = None
    gizmo_rotation: tuple = None

    @staticmethod
    def init_from_world(world: bpy.types.World):
        """ Returns WorldData from bpy.types.World """

        data = WorldData()

        rpr = world.rpr
        if not rpr.enabled:
            return data

        def set_override(override_type):
            if not getattr(rpr, f'{override_type}_override'):
                return

            override_data = WorldData.OverrideData()
            override_data.intensity = rpr.intensity

            image = getattr(rpr, f'{override_type}_image')
            color = getattr(rpr, f'{override_type}_color')
            if image:
                override_data.image = image.name
            else:
                override_data.color = tuple(color)

            override_data.image_type = getattr(rpr, f'{override_type}_image_type', 'SPHERE')

            data.overrides[override_type] = override_data

        data.intensity = rpr.intensity

        if rpr.mode == 'IBL':
            data.ibl = WorldData.IblData.init_from_ibl(rpr.ibl)
        else:
            data.sun_sky = WorldData.SunSkyData(rpr.sun_sky)

        data.gizmo_rotation = tuple(rpr.gizmo_rotation)

        data.overrides = {}
        set_override('background')
        set_override('reflection')
        set_override('refraction')
        set_override('transparency')

        return data

    @staticmethod
    def init_from_shading_data(shading):
        data = WorldData()
        data.intensity = shading.studio_light_intensity
        data.ibl = WorldData.IblData.init_from_shading(shading)
        data.gizmo_rotation = (0.0, 0.0, shading.studio_light_rotate_z)

        bg_data = WorldData.OverrideData()
        if math.isclose(shading.studio_light_background_alpha, 0.0):
            bg_data.intensity = 1.0
            bg_data.color = STUDIO_LIGHT_DEFAULT_COLOR
        else:
            bg_data.intensity = shading.studio_light_background_alpha
            bg_data.studio_light = shading.studio_light
        data.overrides = {'background': bg_data}

        return data

    def export(self, rpr_context):
        def export_override(override_type):
            pyrpr_key = getattr(pyrpr, f'SCENE_ENVIRONMENT_OVERRIDE_{override_type.upper()}')
            override = self.overrides.get(override_type, None)
            # Backplate background override type is handled by render engine
            if override and not (override.image and override.image_type == 'BACKPLATE'):
                rpr_light = rpr_context.scene.environment_overrides.get(pyrpr_key, None)
                if not rpr_light:
                    rpr_light = rpr_context.create_environment_light()
                    rpr_context.scene.add_environment_override(pyrpr_key, rpr_light)

                rpr_light.set_intensity_scale(override.intensity)
                rpr_light.set_group_id(0)

                if override.image:
                    set_light_image(rpr_context, rpr_light, override.image)
                elif override.studio_light:
                    set_light_studio_image(rpr_context, rpr_light, override.studio_light)
                else:
                    rpr_light.set_color(*override.color)

                set_light_rotation(rpr_light, self.gizmo_rotation)

            else:
                if pyrpr_key in rpr_context.scene.environment_overrides:
                    rpr_context.scene.remove_environment_override(pyrpr_key)

        if not self.ibl and not self.sun_sky:
            remove_environment_lights(rpr_context)
            return

        if self.ibl:
            self.ibl.export(rpr_context, self.gizmo_rotation)
        else:
            self.sun_sky.export(rpr_context, self.gizmo_rotation)

        export_override('background')
        export_override('reflection')
        export_override('refraction')
        export_override('transparency')

        rpr_context.scene.environment_light.set_intensity_scale(self.intensity)
        rpr_context.scene.environment_light.set_group_id(0)


def sync(rpr_context: RPRContext, world: bpy.types.World):
    data = WorldData.init_from_world(world)
    data.export(rpr_context)
