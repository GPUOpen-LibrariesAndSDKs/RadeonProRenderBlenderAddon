# rpr_testscript
temporary repo; cannot seem to clone fork of the official RPR Blender Plug-in and contribute to cmd-line tools subdir

## To Run

### Render
python cmd_script.py --blender-path BLENDER_EXE --scene-path BLEND_FILES_SUBDIR --scene-name SCENE

### To Compare Images (Pixel-Wise MSE and SSIM)
python compare_render.py --scene SCENE --ground_truth GROUND_TRUTH_SUBDIR --render RENDER_SUBDIR

## TODO
- need to fix screenshotting as it does render viewport in interactive/fast as well as saves the final rendered image
- separate final render and viewport render into separate command line calls for granularity
- pull crash logs if the program crashes
- add RPR version as an cli arg - need to implement logic that can install/uninstall plugin(s)