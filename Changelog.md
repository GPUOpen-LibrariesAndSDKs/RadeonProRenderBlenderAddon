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