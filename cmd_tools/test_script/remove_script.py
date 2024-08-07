import os
import bpy
import sys
import shutil
import platform


def copy_crash_log(scene, output_dir):
    if platform.system() == 'Windows':
        crash_log_path = os.path.join(os.getenv('LOCALAPPDATA'), 'Temp', f"{scene}.crash.txt")
        if os.path.exists(crash_log_path):
            shutil.copy(crash_log_path, os.path.join(output_dir, f"{scene}.crash.txt"))
            print(f"Copied crash log to {output_dir}")
        else:
            print(f"{crash_log_path} does not exist")
    # TODO: implement pulling from Ubuntu; need a render that will fail for sure to test?
    # prob in var/log/


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


plugin_folder = sys.argv[4]
output_dir = sys.argv[5]
scene = sys.argv[6]

copy_crash_log(scene, output_dir)
remove_script_path(plugin_folder)

