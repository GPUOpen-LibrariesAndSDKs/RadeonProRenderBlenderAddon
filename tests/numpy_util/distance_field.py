import functools

import numpy as np
import imageio

import time

time_start = time.perf_counter()

width, height = 256, 256
#width, height = 3, 3

x, y = np.meshgrid(np.linspace(0, 1, width), np.linspace(0, 1, height))
#print()

from numpy import *


def sphere(center: np.ndarray, radius: np.ndarray, point: np.ndarray):
    r2 = sum(np.square(point - center), axis=-1)
    return sqrt(maximum(square(radius)-r2, 0))


def cone(center, radius, height, point: np.ndarray):
    r2 = sum(np.square(point - center), axis=-1)
    return height*(1-sqrt(r2)/radius)


def torus(center, radius, radius_small, point: np.ndarray):
    r2 = sum(np.square(point - center), axis=-1)

    return sqrt(maximum(square(radius_small)-square(radius-sqrt(r2)), 0))

def prism(center, half_width, height, point: np.ndarray):

    return np.minimum((1.0-np.amax(absolute(point - center), axis=2)/half_width), 0.5)*height

prim = functools.partial

prims = [
    prim(sphere, (0.3, 0.7), 0.25),
    prim(cone, (0.7, 0.3), 0.25, 0.25),
    prim(torus, (0.25, 0.25), 0.125, 0.05),

    prim(prism, (0.75, 0.75), 0.125, 0.5),
]

points = np.concatenate([x[..., np.newaxis], y[..., np.newaxis]], axis=2)

result = np.zeros((width, height), dtype=np.float32)
for prim in prims:
 result =    maximum(result, prim(points))

imageio.imwrite('test.png', result*4)

print("done in:",  time.perf_counter()-time_start)