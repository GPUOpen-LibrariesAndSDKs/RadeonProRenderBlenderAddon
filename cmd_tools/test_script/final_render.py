import os
from pathlib import Path
import sys
import bpy


def print_sys_path():
    print("SYS.PATH FOR final_render.py")
    for i, path in enumerate(sys.path):
        print(f"{i}: {path}")


def create_output_dir(addon_name):
    output_dir = os.path.abspath(addon_name)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    return output_dir


def render_final_image(blender_files, scene, addon_name):

    output_dir = create_output_dir(addon_name)

    bpy.context.scene.render.engine = 'RPR'
    temp_path = os.path.join(blender_files, scene + ".blend")
    scene_path = os.path.abspath(temp_path)

    bpy.ops.wm.open_mainfile(filepath=scene_path)
    bpy.context.scene.rpr.final_render_mode = 'FULL2'  # Set Render Mode to Final
    bpy.context.scene.render.filepath = os.path.join(output_dir, scene + "_final.png")
    bpy.ops.render.render(write_still=True)
    print(f"{scene} rendered successfully at {output_dir}")


def install_and_enable_addon():
    # Set up the addon paths
    src_path = str((Path(__file__).parent.parent.parent/'src').resolve())

    #import sys
    if src_path not in sys.path:
        sys.path.append(src_path)

    import rprblender
    rprblender.register()


def remove_script_path(plugin_folder):
    abs_plugin_folder = os.path.abspath(plugin_folder)
    for script_dir in bpy.context.preferences.filepaths.script_directories:
    #for script_dir in script_directories:
        #if script_dir.directory == abs_plugin_folder:
        bpy.context.preferences.filepaths.script_directories.remove(script_dir)
        bpy.ops.wm.save_userpref()
        print(f"Removed script path from Blender Preferences: {script_dir}")
        #break
    else:
        # do nothing
        pass


def main():

    # print_script_directories()

    blender_files = sys.argv[4]
    scene = sys.argv[5]
    addon_name = sys.argv[6]
    plugin_folder = sys.argv[7]

    import rprblender
    rprblender.register()

    try:
        render_final_image(blender_files, scene, addon_name)
    except Exception as e:
        print(f"Exception: {e}")

    remove_script_path(plugin_folder)


if __name__ == "__main__":
  
    main()
