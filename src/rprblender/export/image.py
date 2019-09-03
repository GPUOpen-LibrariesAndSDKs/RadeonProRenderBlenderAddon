import numpy as np
import os

import bpy
import bpy_extras

from rprblender import utils

from rprblender.utils import logging
log = logging.Log(tag='export.image')


UNSUPPORTED_IMAGES = ('.tiff', '.tif', '.exr')

# image format conversion for packed pixel/generated images
IMAGE_FORMATS = {
    'OPEN_EXR_MULTILAYER': ('OPEN_EXR', 'exr'),
    'OPEN_EXR': ('OPEN_EXR', 'exr'),
    'HDR': ('HDR', 'hdr'),
    'TIFF': ('TIFF', 'tiff'),
    'TARGA': ('TARGA', 'tga'),
    'TARGA_RAW': ('TARGA', 'tga'),
    # everything else will be stored as PNG
}
DEFAULT_FORMAT = ('PNG', 'png')


def key(image: bpy.types.Image):
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


def cache_image_file(image):
    """
    See if image is a file, cache image pixels to temporary folder if not.
    Return image file path.
    """
    if image.source == 'FILE':
        file_path = image.filepath_from_user()
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


def cache_image_file_path(file_path):
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
