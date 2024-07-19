import os
import bpy
import sys
import argparse
import importlib.util
import types


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


def install_and_enable_addon():
    # Set up the addon paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    addon_src_path = os.path.abspath(os.path.join(script_dir, '..', '..', 'src'))
    #pyrprwrap_path = os.path.abspath(os.path.join(script_dir, '..', '..', 'src', 'bindings', 'pyrpr', 'src'))

    # Print paths for debugging purposes
    #print(f"ADDON SRC PATH: {addon_src_path}")
    # print(f"PYRPRWRAP PATH: {pyrprwrap_path}")

    # Append paths to sys.path if not already present
    if addon_src_path not in sys.path:
        sys.path.append(addon_src_path)
    # if pyrprwrap_path not in sys.path:
        #sys.path.append(pyrprwrap_path)

    # # Print sys.path for debugging
    #print(f"sys.path: {sys.path}")

    # # Print contents of the directories
    # print(f"Contents of ADDON SRC PATH: {os.listdir(addon_src_path)}")
    # print(f"Contents of PYRPRWRAP PATH: {os.listdir(pyrprwrap_path)}")

    # Manually create and add the module to sys.modules
    # rprblender = types.ModuleType('rprblender')
    # sys.modules['rprblender'] = rprblender

    # Attempt to import rprblender and register the addon
    try:
        #import pdb; pdb.set_trace()
        import rprblender
        # spec = importlib.util.spec_from_file_location("rprblender", os.path.join(addon_src_path, '__init__.py'))
        # rprblender    Quu ,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,m = importlib.util.module_from_spec(spec)
        # sys.modules["rprblender"] = rprblender
        # spec.loader.exec_module(rprblender)
        # print(f"Contents of rprblender: {dir(rprblender)}")
        rprblender.register()
        print("rprblender addon registered successfully.")
    except ImportError as e:
        print(f"Error importing rprblender: {e}")
    except Exception as e:
        print(f"Error registering rprblender: {e}")


def main():
    # Argument parsing
    parser = argparse.ArgumentParser(description="Render and save a scene in Blender.")
    parser.add_argument('--scene-path', required=True, help='Path to the directory containing the Blender scene files')
    parser.add_argument('--scene-name', required=True, help='Name of the scene to render')

    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])  # Arguments after '--'

    # Install and enable the addon
    install_and_enable_addon()

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
