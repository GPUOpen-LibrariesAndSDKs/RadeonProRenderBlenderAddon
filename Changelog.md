# Version 3.1
## New Features:
- Support for AMD Radeon™ RX 6700 XT graphics cards has been added.
- Cryptomatte AOVs make it easy to filter objects by name or material when using compositors that support Cryptomatte (including the Blender Cryptomatte compositor node)
- A 16-bit Machine Learning Denoiser option is now available to provide for less memory usage and greater speed.
- The speed and responsiveness of the viewport render has been vastly improved under RPR 2.0:
    - An option for using Machine Learning Denoising and Upscaling the viewport render is enabled under the Viewport Settings.  We now render faster at ½ resolution and use the Machine Learning Upscaler to enhance the resolution;
    - Changing the properties tabs no longer restarts the viewport render;
    - Stopping the viewport render is now much faster;
    - Various other fixes to speed up the viewport render have been added.
- An often requested feature, Box mapping in the Image Texture node, is now supported!
- Support for Principled Hair BSDF has been added.
- UV Lookup nodes and math nodes now work in the High, Medium, Low modes.

## Issues Fixed:
- Adaptive sampling now works correctly in the CPU mode.
- All color spaces for textures (not just sRGB and Linear) are now used.
- Noise seeding for animation renders has now fixed an issue of a “swimming” noise pattern.  Noise seeding is always enabled.
- A possible error with UDIM textures has been fixed.
- If the Step Count option in Blender was set to a value > 1, accentuated motion blur would be rendered — fixed.
- Memory was not being freed up at the end of rendering — fixed.
- Shadow Catcher now work with RPR 2.
- An error at the end of rendering with the Full mode has been fixed.
- Calculated values of light power would not update in animation — fixed.
- Transparent background now works with RPR 2.
- Transparent background with tile rendering was creating a lot of artefacts and produced incorrect results — fixed.
- Instances were not updated correctly in the viewport on disabling or enabling: they were correctly removed when disabled but not displayed on enabling — fixed.
- There was an issue with material override application/removal: it reset the object rays visibility settings and was not updated on instances — fixed.
- Linked collection objects now use ray visibility settings, rather than the settings from the parent object.
- Various fixes have been made to .rpr file export:
    - Motion blur is now exported with .rpr export;
    - Export is now implemented with selected engine mode;
    - An image cache is used to save space and enhance speed when exporting.
- Environment Lights and various overrides can now be rotated independently. 
- Area lights were shadowing too aggressively — fixed.
- Switching to contour rendering could fail on an NVidia GPU — fixed.
- Possible crashing when rendering AOVs in the viewport has been fixed.
- Textures could be too blurry due to incorrect MIP mapping, particularly textures in a plane parallel to the camera direction.
- Adaptive sampling now works with RPR 2.
- Spiral artifacts when rendering with both the CPU and GPU have been fixed.
- The Opacity AOV was not taking the maximum ray depth into account — fixed.
- Artifacts in the Depth AOV have been fixed.
- Compiling the BVH geometry has been improved in large scenes.

## Known Issues:
- RPR 2.0 has some forthcoming features.  If these are needed, please use the Legacy render mode:
    - Heterogenous volumes.
- Tiled rendering with transparent background enabled has image artifacts with RPR 2.0.
- Adaptive sampling does not work with CPU only rendering.

# Version 3.0
## New Features:
-   The new plug-in version incorporates version 2.0 of our Radeon™ ProRender system and brings about these significant changes and enhancements:
    - Hardware-accelerated ray tracing on AMD Radeon™ RX 6000 series GPUs
    - Better scaling across multiple devices: the use of two or more GPUs gives a better performance improvement with Radeon ProRender 2.0 than with Radeon ProRender 1.0 in most cases.
    - Less noise for a given number of render samples.  Using the same number of samples as with Radeon ProRender 1.0 may be slower in some scenes, but noise will be significantly lower.  
    - RPR 2.0 is the default render mode called “Full”.  Users who wish to use RPR 1.0 can set the render quality mode to “Legacy”.
    - A new setting for texture cache has been added.  The specified folder will cache textures for rendering, and can be cleaned up by the user if it becomes too large.
- A new setting called “Contour Rendering” allows non-photorealistic outline style renders.
- A setting has been added to allow “Motion Blur only in the Velocity AOV” in the Motion Blur settings.  Enabling this setting means that all AOVs will not have motion blur, but the Velocity AOV will contain motion blur information to allow compositing of post-process motion blur.
- Support for UDIM based tiled image textures has been added

## Issues Fixed:
-   Using the Uber shader with the “Metalness” reflection mode now matches the Disney shader PBR standard more closely. Among other improvements, the Blender “Principled BRDF” node respects the “Specular” parameter better.
-   Motion Blur, particularly for rotation, is now more correct.
-   Animated World settings were not being applied correctly — fixed.
-   An error when using RGB Curve nodes in some instances — fixed.
-   Object and material “Pass Index” Blender’s settings are now fully supported. 
-   Some errors in Hybrid rendering have been resolved.
-   Some users (particularly users with 4GB VRAM GPUs) could not use Hybrid rendering.  We have added a setting for them to use Hybrid in these instances with lower memory.
-   A memory leak when rendering animations has been fixed.
-   An issue involving OpenVDB compatibility with Blender 2.91 has been fixed.  

## Known Issues:
-   RPR 2.0 has some forthcoming features.  If these are needed, please use the “Legacy” render mode:
    - Heterogenous volumes;
    - Adaptive sampling;
    - Adaptive subdivision.
-   The first render on macOS® with RPR 2.0 can take a few minutes to start, while the kernels are being compiled.
macOS® Mojave users should use Legacy mode if seeing crashes with Full mode.
-   Pixelated textures or color artifacts in textures can sometimes happen in Full mode.

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
