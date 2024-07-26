import importlib
# clear cache
importlib.invalidate_caches()

import os
import subprocess
import shutil
import sys
from dotenv import load_dotenv
import zipfile

# unzips addon into the target directory
def extract_addon_to_module(target_dir):
    
    # Extract the ZIP file to the target directory
    with zipfile.ZipFile(addon, 'r') as zip_ref:
        zip_ref.extractall(target_dir)

    print(f"Addon extracted to {target_dir}")


def remove_rprblender(target_dir):
    try:
        addon = os.path.join(target_dir, "rprblender")
        shutil.rmtree(addon, ignore_errors=True)
        print(f"rprblender removed successfully from {target_dir}.")
    except Exception as e:
        print(f"Error removing rprblender: {e}")


def print_sys_path():
    print("SYS.PATH FOR cmd_render.py")
    for i, path in enumerate(sys.path):
        print(f"{i}: {path}")


if __name__ == "__main__":

    load_dotenv()

    sys.path.append("./rprblender")
    script = sys.argv[1]
    blender_path = os.getenv('BLENDER_PATH')
    blender_version = os.path.basename(blender_path).split()[-1]
    blender_exe = os.path.join(blender_path, "blender.exe")

    addon = os.getenv('ADDON_ZIP')
    blender_files = os.getenv('SCENE_PATH')
    scene = os.getenv('SCENE_NAME')
    build = os.path.basename(addon)
    output_dir = os.path.join("Render_Output", os.path.basename(addon))

    ground_truth = os.getenv('GROUND_TRUTH')
    viewport_flag = os.getenv('VIEWPORT_FLAG')

    print(f"Blender Version: {blender_version}")
    print(f"Scene name: {scene}")

    #target_dir = os.path.join(blender_path, blender_version, 'scripts', 'modules')

    target_dir = os.path.join(os.getcwd(), "addon", "modules")

    # extract zip file to blender's modules subdir in scripts
    extract_addon_to_module(target_dir)

    # Always run final_render.py
    final_render_command = [
        blender_exe,
        '--background',
        '--python', script,
        blender_files,
        scene,
        # addon,
        # blender_path,
        # blender_version,
        output_dir

    ]
    subprocess.run(final_render_command)
    
    # Always run compare_render.py after final_render.py
    compare_render_command = [
        'python', 'compare_render.py',
        '--ground-truth-dir', ground_truth,
        '--output-dir', output_dir,
        '--scene-name', scene
    ]
    subprocess.run(compare_render_command)

    # Conditionally run viewport render
    viewport_render_command = [
        blender_path,
        '--python', 'viewport_render.py',
        '--',
        '--scene-path', blender_files,
        '--scene-name', scene,
        '--addon-zip', addon
    ]
    if viewport_flag == 1:
        subprocess.check_call(viewport_render_command)

    remove_rprblender(target_dir)