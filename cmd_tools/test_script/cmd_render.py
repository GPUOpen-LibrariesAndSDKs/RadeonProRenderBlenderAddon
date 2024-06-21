import os
import subprocess
import argparse

def run_blender(blender_path, script_path, scene_path, scene_name):
    script_dir = os.path.dirname(os.path.abspath(script_path))
    
    # Determine if we should run Blender in background mode
    background = not script_path.endswith('viewport_render.py')

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
        "--python",
        script_path,
        "--",
        "--scene-path", scene_path,
        "--scene-name", scene_name
    ]

    if background:
        command.insert(1, "--background")

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
    
    args = parser.parse_args()

    print(f"Blender path: {args.blender_path}")
    print(f"Script path: {args.script_path}")
    print(f"Scene path: {args.scene_path}")
    print(f"Scene name: {args.scene_name}")

    run_blender(args.blender_path, args.script_path, args.scene_path, args.scene_name)
