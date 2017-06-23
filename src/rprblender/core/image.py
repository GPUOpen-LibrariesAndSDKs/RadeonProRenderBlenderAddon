import bpy
import numpy as np

import pyrpr
from pathlib import Path

import rprblender.images
from rprblender import config


def get_core_image_for_blender_image(context, blender_image):
    if config.image_cache_core:
        return rprblender.images.core_image_cache.get_core_image(
            context, blender_image, create_core_image_from_blender_image)
    else:
        return create_core_image_from_blender_image(context, blender_image)


def create_core_image_from_blender_image(context, blender_image):
    filename = bpy.path.abspath(blender_image.filepath)
    if not Path(filename).is_file():
        if config.image_cache_blender:
            pixels = rprblender.images.image_cache.get_image_pixels(blender_image, extract_pixels_from_blender_image)
        else:
            pixels = extract_pixels_from_blender_image(blender_image)
        return create_core_image_from_pixels(context, pixels)
    else:
        use_core_to_load = not filename.endswith('.exr')
        return create_core_image_from_image_file(context, filename, use_core_to_load)


def create_core_image_from_image_file(context, filename, use_core_to_load):
    if config.rpr_image_loading and use_core_to_load:
        handle = pyrpr.Image()
        pyrpr.ContextCreateImageFromFile(context, str(filename).encode('utf8'), handle)
        return handle
    else:
        image = bpy.data.images.load(filename)
        try:
            return create_core_image_from_pixels(context, extract_pixels_from_blender_image(image))
        finally:
            bpy.data.images.remove(image)


def create_core_image_from_pixels(context, pixels):
    desc = pyrpr.ffi.new("rpr_image_desc*")
    desc.image_width = pixels.shape[1]
    desc.image_height = pixels.shape[0]
    desc.image_depth = 0
    desc.image_row_pitch = desc.image_width * pyrpr.ffi.sizeof('rpr_float') * 4
    desc.image_slice_pitch = 0
    handle = pyrpr.Image()
    pyrpr.ContextCreateImage(context,
                             (4, pyrpr.COMPONENT_TYPE_FLOAT32), desc,
                             pyrpr.ffi.cast("float *", pixels.ctypes.data), handle)
    return handle


def extract_pixels_from_blender_image(image):
    raw = np.fromiter(image.pixels, dtype=np.float32, count=image.size[0]*image.size[1]*image.channels)

    assert 4 == image.channels, (image.name, image.channels)

    return np.ascontiguousarray(np.flipud(raw.reshape(image.size[1], image.size[0], 4)))


