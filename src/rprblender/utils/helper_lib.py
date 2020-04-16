#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
import ctypes
import platform
import numpy as np
import math
import os

from . import package_root_dir, IS_WIN

from . import logging
log = logging.Log(tag='utils.helper_lib')


lib = None


class VdbGridData(ctypes.Structure):
    _fields_ = [('x', ctypes.c_int), ('y', ctypes.c_int), ('z', ctypes.c_int),
                ('indices', ctypes.c_void_p), ('indicesSize', ctypes.c_int),
                ('values', ctypes.c_void_p), ('valuesSize', ctypes.c_int)]


def init():
    global lib
    root_dir = package_root_dir()

    OS = platform.system()

    paths = [root_dir]
    if OS == 'Windows':
        lib_name = "RPRBlenderHelper.dll"
        paths.append(root_dir / "../../RPRBlenderHelper/.build/Release")

        if (root_dir / "openvdb.dll").is_file():
            os.environ['PATH'] += ";" + str(root_dir)
        else:
            os.environ['PATH'] += ";" + str((root_dir / "../../ThirdParty/openvdb/bin").absolute())

    elif OS == 'Darwin':
        lib_name = "libRPRBlenderHelper.dylib"
        paths.append(root_dir / "../../RPRBlenderHelper/.build")

    else:
        lib_name = "libRPRBlenderHelper.so"
        paths.append(root_dir / "../../RPRBlenderHelper/.build")

    lib_path = next(p / lib_name for p in paths if (p / lib_name).is_file())
    log('Load lib', lib_path)
    lib = ctypes.cdll.LoadLibrary(str(lib_path))

    # Sun & Sky functions
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

    if IS_WIN:
        # OpenVdb functions
        lib.vdb_read_grids_list.argtypes = [ctypes.c_char_p]
        lib.vdb_read_grids_list.restype = ctypes.c_char_p

        lib.vdb_read_grid_data.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(VdbGridData)]
        lib.vdb_read_grid_data.restype = ctypes.c_bool

        lib.vdb_free_grid_data.argtypes = [ctypes.POINTER(VdbGridData)]

        lib.vdb_get_last_error.restype = ctypes.c_char_p


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


def vdb_read_grids_list(vdb_file):
    grids_list = lib.vdb_read_grids_list(vdb_file.encode('utf8'))
    if not grids_list:
        err_str = lib.vdb_get_last_error().decode('utf8')
        raise RuntimeError(err_str)

    return tuple(grids_list.decode('utf8').split('\n'))


def vdb_read_grid_data(vdb_file, grid_name):
    data = VdbGridData()

    res = lib.vdb_read_grid_data(vdb_file.encode('utf8'), grid_name.encode('utf8'),
                                 ctypes.byref(data))

    if not res:
        err_str = lib.vdb_get_last_error().decode('utf8')
        raise RuntimeError(err_str)

    indices = np.frombuffer((ctypes.c_uint32 * data.indicesSize).from_address(data.indices),
                            dtype=np.uint32).copy()
    values = np.frombuffer((ctypes.c_float * data.valuesSize).from_address(data.values),
                            dtype=np.float32).copy()
    res = {
        'size': (data.x, data.y, data.z),
        'indices': indices.reshape(-1, 3),
        'values': values
    }

    lib.vdb_free_grid_data(ctypes.byref(data))

    return res


init()
