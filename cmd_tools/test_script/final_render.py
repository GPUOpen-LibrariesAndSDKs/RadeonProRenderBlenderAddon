import os
import bpy
import sys
import argparse

def create_output_dir(scene_name):
    output_dir = os.path.abspath(scene_name)
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")
        except OSError as e:
            print(f"Failed to create directory {output_dir}: {e}")
            return None
    return output_dir

def render_final_image(output_file):
    bpy.context.scene.render.engine = 'RPR'
    bpy.context.scene.rpr.final_render_mode = 'FULL2'  # Set Render Mode to Final
    bpy.context.scene.render.filepath = output_file
    bpy.ops.render.render(write_still=True)
    print(f"Final render saved to: {output_file}")

def main():
    # Argument parsing
    parser = argparse.ArgumentParser(description="Render and save a scene in Blender.")
    parser.add_argument('--scene-path', required=True, help='Path to the directory containing the Blender scene files')
    parser.add_argument('--scene-name', required=True, help='Name of the scene to render')

    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])  # Arguments after '--'

    blend_file = os.path.join(args.scene_path, args.scene_name + ".blend")
    
    bpy.ops.wm.open_mainfile(filepath=blend_file)
    
    output_dir = create_output_dir(args.scene_name)
    if not output_dir:
        print("Failed to create output directory. Exiting.")
        return
    
    final_filename = f"{args.scene_name}_final.png"
    final_output_file = os.path.join(output_dir, final_filename)
    
    render_final_image(final_output_file)

if __name__ == "__main__":
    main()
