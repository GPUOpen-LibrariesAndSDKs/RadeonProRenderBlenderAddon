import os
import bpy
import sys


def print_script_directories():
    script_dirs = bpy.context.preferences.filepaths.script_directories
    for i, path in enumerate(script_dirs):
        print(f"Script Path {i + 1}: {path}")

    print(dir(bpy.context.preferences.filepaths.script_directories))
    help(bpy.context.preferences.filepaths.script_directories)


def add_script_path(plugin_folder):
    abs_plugin_folder = os.path.abspath(plugin_folder)
    
    # add the script directory
    bpy.ops.preferences.script_directory_add(directory=abs_plugin_folder)
    print(f"Added script path: {abs_plugin_folder}")
    
    # change name of the script directory entry
    for script_dir in bpy.context.preferences.filepaths.script_directories:
        if script_dir.directory == abs_plugin_folder:
            script_dir.name = plugin_folder
            break

    bpy.ops.wm.save_userpref()


plugin_folder = sys.argv[4]
add_script_path(plugin_folder)