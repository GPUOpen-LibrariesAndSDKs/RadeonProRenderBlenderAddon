import bpy
import importlib

import extract_scene
importlib.reload(extract_scene)

import simple_render
importlib.reload(simple_render)

from pathlib import Path


import time

time_start = time.clock()


extracted = extract_scene.parse_scene(bpy.context.scene)

ensure_extracted = True

if ensure_extracted:
    extracted = list(extracted)

time_extracted = time.clock() 

simple_render.render(
    extracted, 
    (640, 480),
    Path(__file__).parent/'test.png',
    Path(__file__).parent/'rpr_cache')

print('extracted in:', time_extracted-time_start)
print('total execution time in:', time.clock()-time_start) 