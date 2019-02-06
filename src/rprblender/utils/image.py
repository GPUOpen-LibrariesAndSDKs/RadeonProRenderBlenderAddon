import bpy
import numpy as np
import os

from . import key

from . import logging
log = logging.Log(tag='image', level='debug')


def get_rpr_image(rpr_context, image: bpy.types.Image):
    image_key = key(image)
    if image_key in rpr_context.images:
        return rpr_context.images[image_key]

    # Load texture file if provided, it's about 3-5 times faster than loading Blender pixels
    filepath = image.filepath_from_user()
    if filepath and os.path.isfile(filepath):
        return rpr_context.create_image_file(image_key, filepath)

    if image.pixels:
        if image.channels != 4:
            raise ValueError("Image has {} channels; 4 required".format(image.channels), image)

        data = np.fromiter(image.pixels, dtype=np.float32, count=image.size[0] * image.size[1] * image.channels)
        pixels = data.reshape(image.size[1], image.size[0], 4)
        pixels = np.flipud(pixels)
        return rpr_context.create_image_data(image_key, np.ascontiguousarray(pixels))

    if filepath:
        raise ValueError("Unable to load image from file or Blender", image)

    raise ValueError("Image has no data", image)


def create_flat_color_image_data(rpr_context, image_key: str, color: tuple):
    np_image_data = np.full((2, 2, 4), color, dtype=np.float32)
    rpr_image = rpr_context.create_image_data(image_key, np_image_data)
    return rpr_image
