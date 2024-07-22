import os
import subprocess
import argparse


def run_blender(blender_path, script_path, scene_path, scene_name, viewport_flag):
    script_dir = os.path.dirname(os.path.abspath(script_path))
    
    # Determine if we should run Blender in background mode
    background = not script_path.endswith('viewport_render.py')

    # Skip running if viewport_flag is 0 and the script is viewport_render.py
    if script_path.endswith('viewport_render.py') and viewport_flag == 0:
        print("Skipping viewport render since viewport_flag is 0")
        return

    # Get Blender's Python executable path
    blender_python_executable = subprocess.check_output([
        blender_path, "--background", "--python-expr", "import sys; print(sys.executable)"
    ]).decode().strip()

    print(f"Blender Python executable: {blender_python_executable}")

    # Get Blender's site-packages directory
    blender_python_lib = os.path.dirname(blender_python_executable)
    blender_site_packages = os.path.join(blender_python_lib, "lib", "site-packages")
    
    command = [
        blender_path,
        "--background" if background else "",
        "--python", script_path,
        "--",
        "--scene-path", scene_path,
        "--scene-name", scene_name
    ]

    if 'viewport_render.py' in script_path:
        command.extend(["--viewport-flag", str(viewport_flag)])

    # Remove empty strings from command list
    command = [arg for arg in command if arg]

    print(f"Running command: {' '.join(command)}")

    env = os.environ.copy()
    env['PYTHONPATH'] = script_dir + os.pathsep + blender_site_packages + os.pathsep + env.get('PYTHONPATH', '')

    try:
        subprocess.run(command, check=True, env=env)
        print("Blender script executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while running Blender: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wrapper script to run Blender with Python script.")
    parser.add_argument('--blender-path', required=True, help='Path to the Blender executable')
    parser.add_argument('--script-path', required=True, help='Path to the Python script to run within Blender')
    parser.add_argument('--scene-path', required=True, help='Path to the directory containing the Blender scene files')
    parser.add_argument('--scene-name', required=True, help='Name of the scene to render')
    parser.add_argument('--viewport-flag', type=int, required=False, default=0, help='Flag for Viewport Rendering -> 0 for no viewport, 1 for rendering viewport')
    
    args = parser.parse_args()

    print(f"Blender path: {args.blender_path}")
    print(f"Scene name: {args.scene_name}")

    run_blender(args.blender_path, args.script_path, args.scene_path, args.scene_name, args.viewport_flag)
