import bpy
import numpy as np
import os

from . import key

from rprblender.utils import logging
log = logging.Log(tag='export.image')


def sync(rpr_context, image: bpy.types.Image):
    """ Creates pyrpr.Image from bpy.types.Image """

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
