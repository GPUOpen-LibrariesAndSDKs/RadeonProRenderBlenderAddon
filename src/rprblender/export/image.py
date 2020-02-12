import numpy as np
import os

import bpy
import bpy_extras

from rprblender import utils

import pyrpr

from rprblender.utils import logging
log = logging.Log(tag='export.image')


UNSUPPORTED_IMAGES = ('.tiff', '.tif', '.exr')

# image format conversion for packed pixel/generated images
IMAGE_FORMATS = {
    'OPEN_EXR_MULTILAYER': ('OPEN_EXR', 'exr'),
    'OPEN_EXR': ('OPEN_EXR', 'exr'),
    'HDR': ('HDR', 'hdr'),
    # 'TIFF': ('TIFF', 'tiff'), # Seems tiff is not working properly in RPR
    'TARGA': ('TARGA', 'tga'),
    'TARGA_RAW': ('TARGA', 'tga'),
    # everything else will be stored as PNG
}
DEFAULT_FORMAT = ('PNG', 'png')


def key(image: bpy.types.Image):
    """ Generate image key for RPR """
    return image.name


def sync(rpr_context, image: bpy.types.Image):
    """ Creates pyrpr.Image from bpy.types.Image """

    if image.size[0] * image.size[1] * image.channels == 0:
        log.warn("Image has no data", image)
        return None

    image_key = key(image)

    if image_key in rpr_context.images:
        return rpr_context.images[image_key]

    log("sync", image)

    if image.source in ('FILE', 'GENERATED'):
        file_path = cache_image_file(image)
        rpr_image = rpr_context.create_image_file(image_key, file_path)

    else:
        # loading image by pixels
        data = np.fromiter(image.pixels, dtype=np.float32,
                           count=image.size[0] * image.size[1] * image.channels)
        pixels = data.reshape(image.size[1], image.size[0], image.channels)
        pixels = np.flipud(pixels)

        rpr_image = rpr_context.create_image_data(image_key, np.ascontiguousarray(pixels))

    rpr_image.set_name(image_key)

    # TODO: implement more correct support of image color space types
    if image.colorspace_settings.name in ('sRGB', 'BD16', 'Filmic Log'):
        rpr_image.set_gamma(2.2)
    else:
        if image.colorspace_settings.name not in ('Non-Color', 'Raw', 'Linear'):
            log.warn("Ignoring unsupported image color space type",
                     image.colorspace_settings.name, image)

    return rpr_image


class ImagePixels:
    """
    This class stores source image pixels clipped to region size.
    Exports full and sub-region pixels
    """
    def __init__(self, image: bpy.types.Image, region: tuple):
        self.pixels = None
        self.size = (0, 0)
        self.channels = image.channels
        self.name = image.name
        self.color_space = image.colorspace_settings.name

        if image.size[0] * image.size[1] * image.channels == 0:
            log.warn("Image has no data", image)
            return

        self.pixels = self.extract_pixels(image, *region)

        self.size = (region[2] - region[0] + 1, region[3] - region[1] + 1)

    def is_empty(self) -> bool:
        return self.pixels is None

    def extract_pixels(self, image: bpy.types.Image, x1, y1, x2, y2) -> np.array:
        """ Store source image pixels cropped to region coordinates """
        # extract pixels
        data = np.fromiter(image.pixels, dtype=np.float32,
                           count=image.size[0] * image.size[1] * image.channels)
        pixels = data.reshape(image.size[1], image.size[0], image.channels)

        return self.extract_pixels_region(pixels, x1, y1, x2, y2)

    def extract_pixels_region(self, pixels: np.array, x1, y1, x2, y2) -> np.array:
        # crop pixels to region size
        region_pixels = np.array(pixels[y1:y2+1, x1:x2+1, :], dtype=np.float32)

        return region_pixels

    def export_full(self, rpr_context, flipud: bool) -> (pyrpr.Image, None):
        """ Export the full image pixels as RPR image"""
        if self.is_empty():
            return None

        image_key = f"{self.name}@{self.color_space}"

        if image_key in rpr_context.images:
            return rpr_context.images[image_key]

        if flipud:
            pixels = np.ascontiguousarray(np.flipud(self.pixels))
        else:
            pixels = np.ascontiguousarray(self.pixels)
        rpr_image = rpr_context.create_image_data(image_key, pixels)
        rpr_image.set_name(image_key)

        if self.color_space in ('sRGB', 'BD16', 'Filmic Log'):
            rpr_image.set_gamma(2.2)

        return rpr_image

    def export_region(self, rpr_context, x1, y1, x2, y2, flipud: bool) -> (pyrpr.Image, None):
        """ Export pixels cropped to sub-region coordinates as RPR image """
        if self.is_empty():
            return None

        # check sub-region boundaries, just in case something went terribly wrong
        if x1 == x2 or y1 == y2 or x1 >= self.size[0] or x2 < 0 or y1 >= self.size[1] or y2 < 0:
            log.warn(f"Image region ({x1}; {y1})-({x2}; {y2}) has no data", self.name)
            return None

        image_key = f"{self.name}({x1}, {y1})-({x2}, {y2})@{self.color_space}"

        if image_key in rpr_context.images:
            return rpr_context.images[image_key]

        # get pixels region
        pixels = self.extract_pixels_region(self.pixels, x1, y1, x2, y2)
        if flipud:
            pixels = np.flipud(pixels)

        rpr_image = rpr_context.create_image_data(image_key, np.ascontiguousarray(pixels))

        rpr_image.set_name(image_key)

        if self.color_space in ('sRGB', 'BD16', 'Filmic Log'):
            rpr_image.set_gamma(2.2)

        return rpr_image


def cache_image_file(image: bpy.types.Image) -> str:
    """
    See if image is a file, cache image pixels to temporary folder if not.
    Return image file path.
    """

    if image.source == 'FILE':
        file_path = image.filepath_from_user()

        if file_path.lower().endswith('.ies'):
            if os.path.isfile(file_path):
                return file_path

            if not image.packed_file:
                log.warn("Can't load image", image, file_path)
                return None

            file_path = utils.get_temp_pid_dir() / f"{abs(hash(image.name))}.ies"
            if not file_path.is_file():
                # save data of packed file
                file_path.write_bytes(image.packed_file.data)

            return str(file_path)

        if image.is_dirty or not os.path.isfile(file_path) \
                or file_path.lower().endswith(UNSUPPORTED_IMAGES):
            target_format, target_extension = IMAGE_FORMATS.get(image.file_format, DEFAULT_FORMAT)

            # getting file path from image cache and if such file not exist saving image to cache
            file_path = str(utils.get_temp_pid_dir() / f"{abs(hash(image.name))}.{target_extension}")
            if image.is_dirty or not os.path.isfile(file_path):
                current_format = bpy.context.scene.render.image_settings.file_format
                try:
                    # set desired output image file format
                    bpy.context.scene.render.image_settings.file_format = target_format
                    image.save_render(file_path)
                finally:
                    # restore user scene output settings
                    bpy.context.scene.render.image_settings.file_format = current_format

    else:
        file_path = str(utils.get_temp_pid_dir() / f"{abs(hash(image.name))}.png")
        if image.is_dirty or not os.path.isfile(file_path):
            current_format = bpy.context.scene.render.image_settings.file_format
            try:
                # set desired output image file format
                bpy.context.scene.render.image_settings.file_format = 'PNG'
                image.save_render(file_path)
            finally:
                # restore user scene output settings
                bpy.context.scene.render.image_settings.file_format = current_format

    return file_path


def cache_image_file_path(file_path: bpy.types.Image) -> str:
    """ Cache Blender integrated and user-defined LookDev IBL files """
    if not file_path.lower().endswith(UNSUPPORTED_IMAGES):
        return file_path

    if file_path.lower().endswith('.exr'):
        target_format, target_extension = IMAGE_FORMATS['OPEN_EXR']
    else:
        target_format, target_extension = IMAGE_FORMATS['TIFF']

    cache_file_path = str(utils.get_temp_pid_dir() / f"{abs(hash(file_path))}.{target_extension}")
    if os.path.isfile(cache_file_path):
        return cache_file_path

    image = bpy_extras.image_utils.load_image(file_path)
    current_format = bpy.context.scene.render.image_settings.file_format
    try:
        # set desired output image format
        bpy.context.scene.render.image_settings.file_format = target_format
        image.save_render(cache_file_path)
    finally:
        # restore user scene output settings
        bpy.context.scene.render.image_settings.file_format = current_format
        bpy.data.images.remove(image)

    return cache_file_path
