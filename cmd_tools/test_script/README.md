# cmd_tools/test_script
Test Script to automate testing

## To Run

.\render_test.ps1 -BlendFilesSubdir "BLENDFILES" -GroundTruthSubdir "GROUND_TRUTH" -BlenderSubdir "BLENDER_EXE" -Scene "SCENE" -ViewportFlag BOOL

- this will render the final render, compare it via Pixel Wise MSE and SSIM, and optionally render the viewport render

## TODO
- add more granular filepath creation - right now it will just create a SCENE subdir that stores the final render as well as the quant. comparison metrics
- viewport screenshotting