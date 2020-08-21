# Version 2.5.1

## New Features
-   **Beta support for RPR 2.0 and the capability of using it for Viewport Rendering has been added.  This also gives better support for Point and Spot light softness parameters.  For equivalent sample counts, in most scenes, the noise should be lower, and scaling of render speeds across multiple devices should be better.**
-   The ML Denoising filter speed has been improved.
-   The viewport shading panel has been added in the viewport render mode.
-   Support for “Multiply Add” in the Math node has been added (thanks to user cmdrf for their contribution).
-   Support for muting nodes with the “M” key in the shader editor has been added.
-   Support for the Local mode with the “/” key in the viewport has been added.
-   The Object Info node is now supported in the Full mode.
-   The default adaptive tile size has been increased to 32 for adaptive rendering, which gives better results when rendering with multiple GPUs.
A new setting in Viewport Sampling called “Samples per second” has been added, with the default being 15. This setting is roughly analogous to “Frames per second”. The viewport render resolution is adjusted during rendering to try and maintain this interactivity. There is also a “Minimum viewport resolution” setting which limits resolution downscaling. For users with high resolution displays, this adaptive resolution can maintain a much better viewport experience.
-   Support of image sequences of textures and sequences of animated OpenVDB files has been added.
-   Final rendering no longer uses the setting “Update samples”.  Renders are exponentially updated after 1, 1, 2, 4, 8, 16, 32, and every 32 samples thereafter.  This is done to maximize performance, especially with RPR 2.0.  Viewport rendering is unchanged.
-   For users interested in testing the latest developments in the Radeon ProRender for Blender plugin, a weekly “Development Build” will be posted on future Mondays. See https://github.com/GPUOpen-LibrariesAndSDKs/RadeonProRenderBlenderAddon/releases or follow the repository on github to get weekly updates.
-   Support for Blender 2.90

## Fixed Issues
-   The Physical Light normalization  now takes transform scaling into account.
-   Export of .rpr files now uses the scene camera property.
-   Backplate images now work in viewport renders.
-   An issue with image texture gamma correction in Hybrid modes has been fixed.
-   Pixel filter settings are now exported to .rpr files.
-   CPU rendering is now selectable in the UI with RPR 2.0 enabled.
-   Rendering animations can no longer cause a memory leak and eventual crash.
-   Export of .rpr files should no longer be slow with many textures in Blender 2.83.
-   Scene sync and render times are now logged to the console.
-   AOV names in the config.json file exported with .rpr are no longer different from expected names.
-   When using collections of objects with the same name there could be a name duplication leading to some objects not being rendered — fixed.
-   Sometimes switching from the Object to the Edit mode in the viewport could result in the loss of an object’s UV coordinates — fixed.
-   Mapping node transformations were off, in particular, combinations of transforms and rotations only took Z into account — fixed.
-   “Generated” UV in the Texture Coordinate mode is now correct.
-   The scale wrap, sin, cos and tan functions in the vector math node are now not supported.
-   Exporting .rpr files to directories with non-latin characters is now supported
-   Fixed artifacts while using the denoiser with tiled rendering
-   Light Group AOVs and ID’s now use 1-4 instead of selecting a “key” or “fill” light group.

## Known Issues
-   macOS ML denoiser may have issues (driver issue being investigated)
-   RPR 2.0 known issues
    - Shadow and reflection catchers are not yet enabled
    - Adaptive sampling is disabled
    - Adaptive subdivision is disabled
    - On macOS, currently RPR 2.0 uses OpenCL and not metal.
    - Volumetric absorption does not currently work


# Version 2.4.11

## NEW FEATURES:

-   **Installers are now simply zip packages. To install, load the add-on through the Blender add-on preferences menu and point to the zip file.**
    
-   macOS now supports ML Denoising.
    
-   Support for Blender 2.83 has been added.
    
-   Support for reading OpenVDB files via Blender 2.83 “Volume” objects has been added.
    
-   The RPR 2.0 “experimental” render mode has been added. Currently this is Windows only and only recommended for final rendering. This is a prototype of our next generation renderer. Performance and memory usage should now be improved, especially for complex scenes. Multi-GPU and CPU + GPU performance, particularly when rendering with an AMD CPU + AMD GPU, is dramatically improved. For complex scenes that are larger than video memory size, out-of-core textures and geometry are automatic.
    
-   Baking nodes. We have added utilities for baking nodes. This is useful with nodes that RPR does not translate natively, such as noise texture nodes. It is also quite useful with complex node networks, as they run faster at render time. There are two options:
    
     Select an object and material. In the Shader Editor, select the nodes you wish to bake, and press the “Bake Selected Nodes” button. The nodes will be baked to textures, and texture read nodes will be created;
    
     In the render settings, press the “Bake All Unknown Nodes” button. All nodes that RPR does not translate will be baked to textures.
    
    Please note that after changing node setups, the nodes will need to be re-baked.

-   There is a new GL_Interop setting under “Viewport Sampling” settings. Users who use external GPUs (eGPUs) for viewport rendering may need to disable this.
    
-   The speed of export of images for rendering has been increased.
    
-   Support has been added for reading OpenVDB files via Blender 2.83 “Volume” objects.
    
-   Node improvements:
    Volume “Temperature” settings in the Principled Volume nodes has been enabled;
    Support for Object mode in the Texture Coordinate node has been added;
    Support has been added for the RGB Mix node modes: overlay, lighten, screen, linear and soft light;
    The Bump node now uses the Normal input;
    Hair BSDF is now closer to Cycles’ renders.
    

  

## Bug Fixes:

-   When rendering in multiple GPUs, adaptive sampling can no longer be "unbalanced" leading to artifacts with noisier areas.
    
-   Hair can now be modified while viewport rendering.
    
-   Errors have been fixed that are possible when exporting images with complex scenes.
    
-   Using the “Transparent Background” option with the denoiser can no longer lead to a black image.
    
-   The number of aperture blades for Depth of Field is no longer applied incorrectly.
    
-   Transparent Background in the viewport has been enabled.
    
-   Issues with shadow and reflection catchers have been fixed.
    
-   A bug when enabling and disabling while viewport rendering has been fixed.
    
-   Hair not showing up on a linked model: has been fixed.
    
-   Smoke rendering with noise enabled has been fixed.
    
-   An issue with curve objects with empty materials has been fixed.
    
-   Registering the Plug-in and scanning for devices is now faster.
    
-   Hair with differing root and tip radii match Cycles better now, including the “closed tip” option.
    

  
  

## Known Issues:

-   An installed Plug-in on Windows cannot be upgraded while the Plug-in is enabled. Users must disable the installed Plug-in, restart Blender and then install the new Plug-in.
    
-   ML Denoiser on macOS (with certain Vega cards) and Ubuntu can produce black pixels.
    
-   Viewport rendering with RPR 2.0 falls back to use RPR 1.0.

    
-   Invisible area lights can cause firefly artifacts in RPR 2.0.
