import bpy
import addon_utils

from pathlib import Path
import shutil

addon_name = 'rprblender'

# disable addon first
addon_utils.disable(addon_name, default_set=True)

# find addon package and remove its folder
for mod in addon_utils.modules():
    if addon_name == mod.__name__:
        filepath = Path(mod.__file__)
        if filepath.exists():
            addon_dir = filepath.parent
            if addon_name == addon_dir.name:
                print('removing', addon_dir)
                shutil.rmtree(str(addon_dir))

# this operator fails in --background mode by trying to call context.area.tag_redraw
# bpy.ops.preferences.addon_remove(module='rprblender')
bpy.ops.wm.save_userpref()
