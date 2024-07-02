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


def load_and_register_addon(addon_path):
    if addon_path not in sys.path:
        sys.path.append(addon_path)
    for addon in os.listdir(addon_path):
        if addon.endswith(".py"):
            addon_name = addon[:-3]
            try:
                bpy.ops.wm.addon_install(filepath=os.path.join(addon_path, addon))
                bpy.ops.wm.addon_enable(module=addon_name)
                print(f"Addon {addon_name} installed and enabled.")
            except Exception as e:
                print(f"Error installing addon {addon_name}: {e}")


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
    parser.add_argument('--addon-path', required=True, help='Path to the addon directory')

    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])  # Arguments after '--'

    blend_file = os.path.join(args.scene_path, args.scene_name + ".blend")
    
    bpy.ops.wm.open_mainfile(filepath=blend_file)

    # Import and register the rprblender addon
    try:
        sys.path.append(args.addon_path)
        import rprblender
        rprblender.register()
        print("rprblender addon registered successfully.")
    except ImportError as e:
        print(f"Error importing rprblender: {e}")
    except Exception as e:
        print(f"Error registering rprblender: {e}")
    
    output_dir = create_output_dir(args.scene_name)
    if not output_dir:
        print("Failed to create output directory. Exiting.")
        return
    
    final_filename = f"{args.scene_name}_final.png"
    final_output_file = os.path.join(output_dir, final_filename)
    
    render_final_image(final_output_file)


if __name__ == "__main__":
    main()
