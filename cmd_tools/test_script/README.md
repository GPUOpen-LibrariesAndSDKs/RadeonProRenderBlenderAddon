# rpr_testscript
temporary repo; cannot seem to clone fork of the official RPR Blender Plug-in and contribute to cmd-line tools subdir

## To Run

### Render
 .\render_test.ps1 -BlendFilesSubdir "BLENDFILES" -GroundTruthSubdir "GROUND_TRUTH" -BlenderSubdir "BLENDER_EXE" -Scene "SCENE"

 - this will render the final render, compare it via Pixel Wise MSE and SSIM, and render the viewport render

## TODO
- add more granular filepath creation - right now it will just create a SCENE subdir that stores the final render as well as the quant. comparison metrics
- viewport screenshotting
- pull crash logs if the program crashes
- add RPR version as an cli arg - need to implement logic that can install/uninstall plugin(s)