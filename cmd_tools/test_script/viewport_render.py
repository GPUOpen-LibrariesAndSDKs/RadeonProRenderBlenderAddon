import os
import bpy
import sys
import argparse


def set_output_path(subdir_name):
    output_dir = os.path.abspath(subdir_name)
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")
        except OSError as e:
            print(f"Failed to create directory {output_dir}: {e}")
            return None
    return output_dir


# def render_viewport_image(output_dir, filename):
#     class RenderViewportOperator(bpy.types.Operator):
#         bl_idname = "wm.render_viewport_operator"
#         bl_label = "Render Viewport Operator"

#         def execute(self, context):
#             for window in bpy.context.window_manager.windows:
#                 for area in window.screen.areas:
#                     if area.type == 'VIEW_3D':
#                         for space in area.spaces:
#                             if space.type == 'VIEW_3D':
#                                 space.shading.type = 'RENDERED'
#                                 break
#                         break

#             bpy.context.scene.rpr.viewport_render_mode = 'FULL2'  # Set Viewport Mode to Final

#             # Wait for the viewport to update
#             bpy.context.view_layer.update()

#             # Use a timer to ensure the viewport is fully updated
#             bpy.app.timers.register(self.delayed_render, first_interval=3.0)  # Adjust the interval as needed

#             return {'RUNNING_MODAL'}

#         def delayed_render(self):
#             output_filepath = f"{output_dir}/{filename}"
#             bpy.context.scene.render.filepath = output_filepath

#             for window in bpy.context.window_manager.windows:
#                 for area in window.screen.areas:
#                     if area.type == 'VIEW_3D':
#                         with bpy.context.temp_override(window=window, area=area, region=area.regions[-1]):
#                             bpy.ops.render.opengl(write_still=True)

#                         print("VIEWPORT RENDER IS FINISHED")
#                         return None  # Unregister the timer

#             return 1.0  # Retry if not successful

#     bpy.utils.register_class(RenderViewportOperator)

#     # Execute the operator
#     bpy.ops.wm.render_viewport_operator()


def render_viewport_image(output_dir, filename):
    #bpy.context.scene.rpr.viewport_mode = 'FINAL'

    for area in bpy.context.window_manager.windows[0].screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'RENDERED'
                    #space.shading.render_pass = 'FINAL'  # Set Viewport Mode to Final
                    break
            break

    bpy.context.scene.rpr.viewport_render_mode = 'FULL2'  # Set Viewport Mode to Final

    # Wait for the viewport to update
    bpy.context.view_layer.update()


    # screenshot_path = os.path.join(output_dir, filename)
    # bpy.ops.screen.screenshot(filepath=screenshot_path)
    # print(f"Viewport render saved to: {screenshot_path}")


def install_and_enable_addon():
    # Set up the addon paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    addon_src_path = os.path.abspath(os.path.join(script_dir, '..', '..', 'src'))

    # Append paths to sys.path if not already present
    if addon_src_path not in sys.path:
        sys.path.append(addon_src_path)

    # Attempt to import rprblender and register the addon
    try:
        #import pdb; pdb.set_trace()
        import rprblender
        rprblender.register()
        print("rprblender addon registered successfully.")
    except ImportError as e:
        print(f"Error importing rprblender: {e}")
    except Exception as e:
        print(f"Error registering rprblender: {e}")


def main():
    print("Starting viewport render script...")

    # import bpy

    # # Get the RPR settings object
    # rpr_settings = bpy.context.scene.rpr

    # # Print all attributes and their current values
    # for attr in dir(rpr_settings):
    #     # Skip private attributes and methods
    #     if not attr.startswith("_"):
    #         try:
    #             value = getattr(rpr_settings, attr)
    #             print(f"{attr}: {value}")
    #         except AttributeError:
    #             # Some attributes may not be accessible
    #             print(f"{attr}: <not accessible>")

    # Argument parsing
    parser = argparse.ArgumentParser(description="Render and save a viewport render in Blender.")
    parser.add_argument('--scene-path', required=True, help='Path to the directory containing the Blender scene files')
    parser.add_argument('--scene-name', required=True, help='Name of the scene to render')
    parser.add_argument('--viewport-flag', type=int, required=True, help="Flag to enable viewport render")

    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:]) 

    print(f"Scene path: {args.scene_path}")
    print(f"Scene name: {args.scene_name}")
    
    if args.viewport_flag == 1:
        blend_file = os.path.join(args.scene_path, args.scene_name + ".blend")
        print(f"Loading blend file: {blend_file}")
        
        bpy.ops.wm.open_mainfile(filepath=blend_file)
        
        output_dir = set_output_path(args.scene_name)
    
        viewport_filename = f"{args.scene_name}_viewport.png"
        install_and_enable_addon()
        render_viewport_image(output_dir, viewport_filename)
    else:
        print("Viewport render is disabled.")


if __name__ == "__main__":
    main()
