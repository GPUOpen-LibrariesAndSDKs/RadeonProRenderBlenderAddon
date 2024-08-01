## .ENV Variables
SCENE_PATH={directory containing blend files to be tested}   
GROUND_TRUTH={dir containing rendered image to compare to for MSE and SSIM (assumes the image is called {scene}_actual)}  
VIEWPORT_FLAG={0 for no viewport rendering, 1 for viewport}  

PLUGIN={name of the relative directory where the plugin will be unzipped to}  
RENDER_OUTPUT_DIR={name fo the directory where the output and comparison txt will be put}  

SCENE_NAME={name of scene}  
BLENDER_PATH=C:\Program Files\Blender Foundation\Blender {VERSION}  
ADDON_ZIP={where build artifact zip is located}  


## Run Instructions
Set .env Variables  

Run with `./run_render.cmd` on Windows  
Run with `./run_render.sh` on Ubuntu/Linux

Assumes that the ground truth files to compare against are called {SCENE}_actual.png


