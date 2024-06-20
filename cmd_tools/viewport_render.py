import bpy
import os
import sys
import time

def set_output_path(subdir_name):
    # Create a subdirectory if it does not exist
    output_dir = os.path.join(subdir_name)
    # if not os.path.exists(output_dir):
    #     try:
    #         os.makedirs(output_dir)
    #         print(f"Created directory: {output_dir}")
    #     except OSError as e:
    #         print(f"Failed to create directory {output_dir}: {e}")
    #         return None
    return output_dir

def render_viewport_image(output_dir, filename):
    # Set the viewport shading to 'RENDERED'
    for area in bpy.context.window_manager.windows[0].screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'RENDERED'
                    break
            break

    # Wait for the viewport to update
    #time.sleep(10)

    # Take a screenshot of the viewport
    # screenshot_path = os.path.join(output_dir, filename)
    # bpy.ops.screen.screenshot(filepath=screenshot_path)
    # print(f"Viewport render saved to: {screenshot_path}")

def main(scene_path, scene_name):
    # Set the base directory name to the scene name
    output_dir = set_output_path(scene_name)

    # Define file names
    viewport_filename = f"{scene_name}_viewport.png"

    # Render the viewport image
    render_viewport_image(output_dir, viewport_filename)

if __name__ == "__main__":
    scene_path = sys.argv[-2]
    scene_name = sys.argv[-1]

    # Load the specified Blender scene
    blend_file = os.path.join(scene_path, f"{scene_name}.blend")
    bpy.ops.wm.open_mainfile(filepath=blend_file)

    main(scene_path, scene_name)