## .ENV Variables
set .env variables for 
SCENE_PATH={directory containing blend files to be tested}   
GROUND_TRUTH={dir containing rendered image to compare to for MSE and SSIM (assumes the image is called {scene}_actual)}  
VIEWPORT_FLAG={0 for no viewport rendering, 1 for viewport}  

PLUGIN={name of the relative directory where the plugin will be unzipped to}  

SCENE_NAME={name of scene}  
BLENDER_PATH=C:\Program Files\Blender Foundation\Blender {VERSION}  
ADDON_ZIP={where build artifact zip is located}  


## Run Instructions
Run with `./run_render.cmd`



