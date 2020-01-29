import bpy
from pathlib import Path

bpy.ops.preferences.addon_install(overwrite=True, filepath=r'/Users/Shared/RadeonProRender/Blender/addon/addon.zip')
bpy.ops.preferences.addon_enable(module='rprblender')
bpy.ops.wm.save_userpref()

