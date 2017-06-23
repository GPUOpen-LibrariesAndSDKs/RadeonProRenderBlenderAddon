import sys
import os

import time

import numpy as np
from pathlib import Path


root = Path(__file__).parents[2]

os.environ['PATH'] = os.environ['PATH']+os.pathsep+str(root/'ThirdParty/RadeonProRender SDK/Win/bin')

import ctypes

lib = ctypes.CDLL(str(root/'RPRBlenderHelper/.build/Release/RPRBlenderHelper.dll'))

lib.set_sun_horizontal_coordinate.argtypes = [ctypes.c_float, ctypes.c_float]
lib.set_sun_time_location.argtypes = [ctypes.c_float, ctypes.c_float,
                                      ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_float, ctypes.c_bool]
lib.set_sky_params.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float,
                               ctypes.c_void_p, ctypes.c_void_p]

lib.generate_sky_image.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]

lib.generate_sky_image.restype = ctypes.c_bool
lib.get_sun_azimuth.restype = ctypes.c_float
 

width = 1024
height = width

image = np.empty((width, height, 3), dtype=np.float32)
p = image.ctypes.data

time_start = time.perf_counter()

filter_color = np.array([0, 0, 0], dtype=np.float32)
ground_color = np.array([0.4, 0.4, 0.4], dtype=np.float32)

lib.set_sun_horizontal_coordinate(0, 30)

lib.set_sky_params(0.2, 1.0, 0.5,
                   0.001, 0.1, 0.5,
                   filter_color.ctypes.data, ground_color.ctypes.data)

count = 10
for i in range(count):
    assert lib.generate_sky_image(width, height, p)

time_elapsed = time.perf_counter()-time_start
print("%dx%d"%(width, height), "time:", time_elapsed, "(%f per call)"%(time_elapsed/count))

import imageio
imageio.imwrite('test.png', (np.clip(image, a_min=0, a_max=1)*255).astype(dtype=np.uint8))

