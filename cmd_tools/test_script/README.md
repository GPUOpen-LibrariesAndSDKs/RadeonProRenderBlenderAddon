## .ENV Variables
set .env variables for 
    BLENDER_PATH=C:\Program Files\Blender Foundation\Blender {VERSION}  
    ADDON_ZIP={where build artifact zip is located}  
    SCENE_PATH={directory containing blend files to be tested}  
    SCENE_NAME={name of scene}  
    GROUND_TRUTH={rendered image to compare to for MSE and SSIM}  
    VIEWPORT_FLAG={0 for no viewport rendering, 1 for viewport}  


## Run Instructions
Run with `./run_render.cmd`


## Directory Structure

- **{plugin}/**: parent directory for the plugin.
  - **addons/**: 
  - **modules/**:
    - **{rprblender_build}/**: Specific build for the `rprblender` module.
  - **startup/**: 


### Instructions 
Make sure the {plugin} parent directory shown above is added in this fashion in Script Directories

![{Plugin} Parent Dir is named "addon"](assets\python_module_preferences.png)

Reference: https://blender.stackexchange.com/questions/5287/using-3rd-party-python-modules


