import multiprocessing
from pathlib import Path
import math
import platform
import os
import shutil

import bpy
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


# saving current process id
PID = os.getpid()


from . import logging
log = logging.Log(tag='utils')


def get_temp_dir():
    """ Returns $TEMP/rprblender temp dir. Creates it if needed """

    temp_dir = Path(os.environ.get('TEMP', "C:\\Temp")) if platform.system() == 'Windows' else \
               Path("/tmp")

    temp_dir /= "rprblender"

    if not os.path.isdir(temp_dir):
        log("Creating temp dir", temp_dir)
        os.mkdir(temp_dir)

    return temp_dir


def get_temp_pid_dir():
    """ Returns $TEMP/rprblender/PID temp dir for current process. Creates it if needed """

    pid_dir = get_temp_dir() / str(PID)
    if not os.path.isdir(pid_dir):
        log(f"Creating image temp pid dir {pid_dir}")
        os.mkdir(pid_dir)

    return pid_dir


def clear_temp_dir():
    """ Clears whole $TEMP/rprblender temp dir """

    temp_dir = get_temp_dir()
    names = os.listdir(temp_dir)
    if not names:
        return

    log("Clearing temp dir", temp_dir)
    for name in names:
        path = temp_dir / name
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.remove(path)
