import bpy
from pathlib import Path

addon_script_path = Path(__file__).parent.parent.parent/'src/tools/load_addon.py'

filepath = str(addon_script_path)
global_namespace = {"__file__": filepath, "__name__": "__main__"}
with open(filepath, 'rb') as file:
    exec(compile(file.read(), filepath, 'exec'), global_namespace)


bpy.context.scene.render.engine = 'RPR'


bpy.context.scene.render.filepath = str(Path().resolve()/'test.png')
bpy.ops.render.render(write_still=True)

