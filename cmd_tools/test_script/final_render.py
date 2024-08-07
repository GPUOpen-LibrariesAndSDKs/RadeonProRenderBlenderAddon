import os
from pathlib import Path
import sys
import bpy
import shutil
import platform


def print_sys_path():
    print("SYS.PATH FOR final_render.py")
    for i, path in enumerate(sys.path):
        print(f"{i}: {path}")


def create_output_dir(addon_name):
    output_dir = os.path.abspath(addon_name)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    return output_dir


def clear_crash_log(scene):
    if platform.system() == 'Windows':
        crash_log_path = os.path.join(os.getenv('LOCALAPPDATA'), 'Temp', f"{scene}.crash.txt")
        if os.path.exists(crash_log_path):
            os.remove(crash_log_path)
            print(f"Cleared existing crash log: {crash_log_path}")
        else:
            print(f"{crash_log_path} does not exist")
            
    # TODO: implement pulling from Ubuntu; need a render that will fail for sure to test?
    # prob in var/log/


def render_final_image(blender_files, scene, output_dir):
    clear_crash_log(scene)
    
    # this try-catch seems to be unnecessary since copying the error log accomplishes the same thing 
    # plus it doesnt seem to "function" correctly since a failed render doesnt hit the catch
    #try:
    bpy.context.scene.render.engine = 'RPR'
    temp_path = os.path.join(blender_files, scene + ".blend")
    scene_path = os.path.abspath(temp_path)

    bpy.ops.wm.open_mainfile(filepath=scene_path)
    bpy.context.scene.rpr.final_render_mode = 'FULL2'  # Set Render Mode to Final
    bpy.context.scene.render.filepath = os.path.join(output_dir, scene + "_final.png")
    bpy.ops.render.render(write_still=True)
    print(f"{scene} rendered successfully at {output_dir}")
    # except Exception as e:
    #     error_log_path = os.path.join(output_dir, f"{scene}_error_log.txt")
    #     with open(error_log_path, 'w') as error_log_file:
    #         error_log_file.write(str(e))
    #     print(f"Error when trying to render: {e}. Check {error_log_path} for details.")


def install_and_enable_addon():
    # Set up the addon paths
    src_path = str((Path(__file__).parent.parent.parent/'src').resolve())

    #import sys
    if src_path not in sys.path:
        sys.path.append(src_path)

    import rprblender
    rprblender.register()


def main():

    blender_files = sys.argv[4]
    scene = sys.argv[5]
    addon_name = sys.argv[6]

    import rprblender
    rprblender.register()

    output_dir = create_output_dir(addon_name)
    render_final_image(blender_files, scene, output_dir)


if __name__ == "__main__":
  
    main()
