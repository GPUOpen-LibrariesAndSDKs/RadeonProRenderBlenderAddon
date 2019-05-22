import ctypes
import platform
import numpy as np
import math
import os

from . import package_root_dir

from . import logging
log = logging.Log(tag='utils.helper_lib')


lib = None


def init():
    global lib
    root_dir = package_root_dir()

    if platform.system() == 'Windows':
        paths = (root_dir / "RPRBlenderHelper.dll",
                 root_dir / "../../RPRBlenderHelper/.build/Release/RPRBlenderHelper.dll")
    elif 'Darwin' == platform.system():
        paths = (root_dir / "libRPRBlenderHelper.dylib",
                 root_dir / "../../RPRBlenderHelper/.build/libRPRBlenderHelper.dylib")
    else:
        paths = (root_dir / "libRPRBlenderHelper.so",
                 root_dir / "'../../RPRBlenderHelper/.build/libRPRBlenderHelper.so")

    for path in paths:
        if not os.path.isfile(path):
            continue

        try:
            log('Load lib', path)
            lib = ctypes.cdll.LoadLibrary(str(path))
            break
        except OSError as e:
            log.critical('Failed to load', path, e)

    assert lib

    lib.set_sun_horizontal_coordinate.argtypes = [ctypes.c_float, ctypes.c_float]

    lib.set_sun_time_location.argtypes = [ctypes.c_float, ctypes.c_float,
                                          ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                          ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                          ctypes.c_float, ctypes.c_bool]

    lib.set_sky_params.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float, 
                                   ctypes.c_float, ctypes.c_float, ctypes.c_float,
                                   ctypes.c_void_p, ctypes.c_void_p]

    lib.generate_sky_image.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    lib.generate_sky_image.restype = ctypes.c_bool

    lib.get_sun_azimuth.restype = ctypes.c_float
    lib.get_sun_altitude.restype = ctypes.c_float


def set_sun_horizontal_coordinate(azimuth: float, altitude: float):
    lib.set_sun_horizontal_coordinate(math.degrees(azimuth), math.degrees(altitude))


def set_sun_time_location(
        latitude: float, longitude: float,
        year: int, month: int, day: int,
        hours: int, minutes: int, seconds: int,
        time_zone: float, daylight_savings: bool
):
    lib.set_sun_time_location(
        latitude, longitude,
        year, month, day, hours, minutes, seconds,
        time_zone, daylight_savings
    )


def set_sky_params(
        turbidity: float, sun_glow: float, sun_disc: float,
        horizon_height: float, horizon_blur: float, saturation: float,
        filter_color: tuple, ground_color: tuple
):
    filter_color_arr = np.array(filter_color, dtype=np.float32)
    ground_color_arr = np.array(ground_color, dtype=np.float32)

    lib.set_sky_params(
        turbidity, sun_glow, sun_disc,
        horizon_height, horizon_blur, saturation,
        ctypes.c_void_p(filter_color_arr.ctypes.data), ctypes.c_void_p(ground_color_arr.ctypes.data)
    )


def generate_sky_image(width, height) -> np.array:
    im = np.ones((width, height, 3), dtype=np.float32)
    if not lib.generate_sky_image(width, height, ctypes.c_void_p(im.ctypes.data)):
        return None

    return im


def get_sun_horizontal_coordinate() -> (float, float):
    return lib.get_sun_azimuth(), lib.get_sun_altitude()


init()
