from dataclasses import dataclass
import multiprocessing
from pathlib import Path
import math

import bpy
import mathutils
import rprblender


def is_rpr_active(context: bpy.types.Context):
    return context.scene.render.engine == 'RPR'


def package_root_dir():
    return Path(rprblender.__file__).parent


def get_cpu_threads_number():
    return multiprocessing.cpu_count()


def tile_iterator(tile_order, width, height, tile_width, tile_height):
    """
    Returns iterator function depending of tile_order.
    Also iterator functions has 'len' field which consists number of tiles

    :param tile_order: could be 'VERTICAL', 'HORIZONTAL', 'CENTER_SPIRAL'
    :param width: render width
    :param height: render height
    :param tile_width: max tile width
    :param tile_height: max tile height
    :return: ((tile_x, tile_y), (tile_w, tile_h)) by every iterator call
    """
    def get_tiles_vertical():
        for x in range(0, width, tile_width):
            for y in range(height, 0, -tile_height):
                y1 = max(y - tile_height, 0)
                yield (x, y1), (min(tile_width, width - x), min(tile_height, y - y1))

    def get_tiles_horizontal():
        for y in range(height, 0, -tile_height):
            y1 = max(y - tile_height, 0)
            for x in range(0, width, tile_width):
                yield (x, y1), (min(tile_width, width - x), min(tile_height, y - y1))

    def get_tiles_center_spiral():
        x = (width - tile_width) // 2
        y = (height - tile_height) // 2

        def get_tile():
            if x + tile_width > 0 and x < width and y + tile_height > 0 and y < height:
                x1 = max(x, 0)
                y1 = max(y, 0)
                x2 = min(x + tile_width, width)
                y2 = min(y + tile_height, height)
                return (x1, y1), (x2 - x1, y2 - y1)

            return None

        tile = get_tile()
        if tile:
            yield tile

        side = 0
        have_tiles = True
        while have_tiles:
            have_tiles = False

            side += 1
            for _ in range(side):
                y -= tile_height
                tile = get_tile()
                if tile:
                    have_tiles = True
                    yield tile
            for _ in range(side):
                x += tile_width
                tile = get_tile()
                if tile:
                    have_tiles = True
                    yield tile
            side += 1
            for _ in range(side):
                y += tile_height
                tile = get_tile()
                if tile:
                    have_tiles = True
                    yield tile
            for _ in range(side):
                x -= tile_width
                tile = get_tile()
                if tile:
                    have_tiles = True
                    yield tile

    def get_tiles_number():
        if tile_order != 'CENTER_SPIRAL':
            x_count = math.ceil(width / tile_width)
            y_count = math.ceil(height / tile_height)
        else:
            x = (width - tile_width) // 2
            y = (height - tile_height) // 2

            x_count = math.ceil(x / tile_width) + math.ceil((width - x) / tile_width)
            y_count = math.ceil(y / tile_height) + math.ceil((height - y) / tile_height)

        return x_count * y_count

    tile_func = {
        'VERTICAL': get_tiles_vertical,
        'HORIZONTAL': get_tiles_horizontal,
        'CENTER_SPIRAL': get_tiles_center_spiral,
    }[tile_order]

    # adding 'len' field into function object
    tile_func.len = get_tiles_number()

    return tile_func
