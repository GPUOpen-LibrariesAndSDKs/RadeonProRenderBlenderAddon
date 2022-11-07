# Version 3.5
## New Features:
- Support for Blender 3.3 and Blender 3.4 has been added, including support for the new hair system.
- The RPR Interactive mode has been improved with the following developments:
  - Better support for more shader node types;
  - Even faster rendering with optimized settings out of the box;
  - Hair rendering support;
  - More AOVs supported;
  - Support for OpenColorIO texture spaces;
  - Shadow Catcher support;
  - Per face materials are supported;
  - IES lights are now supported.
- A new Bevel Shader node has been added. This can be used to create small rounded edges on objects. In the physical world, objects rarely have completely sharp edges like polygons. Using this node will enhance the details of artists’ renders.
- Support for the Double Sided node has been added, which allows attaching a different shader to each side of an object mesh.
- The “Pixel Filter” (anti-aliasing) setting for the RPR Final mode has been re-enabled.

## Bugs Fixed:
- Contour outline settings using the “UV threshold” for setting the Outline have been fixed.
- The Temperature, Velocity and Heat settings in the Principled Volume Shader node have been fixed. Attributes are now supported as well.
- Fixed an issue where smoke simulations were scaled incorrectly — fixed.
- OpenVDB sequences of files are now supported.
- Hair Particle type exporting has been optimized.
- The issue has been fixed where a “halo” could appear around objects with a shadow catcher or reflection catcher attached.
- Emissive objects with transparent shadows could cast the wrong shadow — fixed.
- Reflection catcher was not “catching” emission lights — fixed.

## Known Issues:
- In some scenes, the hardware feature Smart Access Memory can cause slower renders with the RPR Final mode.


# Version 3.4
## New Features:
- Support for Blender 3.1 and 3.2 has been added.
- A new option for overriding an object’s ability to receive shadows has been added.  If this option is set to false, shadows from other objects will not be shown.
- Support for Atmosphere and Fog in the World Properties Panel has been added.  Artists can now add a dense (or sparse) fog to render real world atmospheres more realistically.  There are settings for density, falloff, height above the ground, and more.
- Support for the Map Range node (linear mode) has been added.
- Hair now works with the RPR Interactive mode.
- A setting has been added to change the Random Seed for renders (similar to Blender’s Cycles feature), which allows changing the noise pattern.
- An option has been to use the secondary UV set for creating the outlines in toon renders.

## Fixes:
- Partially transparent and reflective Uber shaders could be darker than physically correct — fixed.
- Incorrect rotational motion blur has been fixed.
- Issues with IES lights and atmosphere volumes have been fixed.
- Albedo AOV now shows the mid color of toon shaders.
- The Blender spot light parameter “Spot Blend” now works as expected.
- An exception that could happen with unsupported material nodes has been fixed.
- An error could occur when changing frames when viewport rendering was running — fixed.
- Better response is seen now when viewport rendering is active and the camera is moved.
- Better checking has been achieved for the need to update viewport renders when selecting an object.
- Depth AOV support for Blender 3.0.1 and above has been fixed.
- Errors could occur when viewport render and material previews happening simultaneously — fixed.
- A crash could occur with the RPR Interactive mode and unsupported AOVs — fixed.
- Support for Geometry nodes in viewport and final rendering has been fixed and improved.
- An error with “halo” type particles in Blender 3.0 and above has been corrected.
- Object Index, Material Index and Random in the Object Info node — fixed.
Cryptomatte AOVs work again in the Blender Compositor.
- An issue where the mesh in Edit mode could be missing in Blender 3.1 and above — fixed.
- OpenVDB volume support for Blender 3.2 has been re-enabled (the OpenVDB version was changed in Blender).

# Version 3.3.16
## New Features:
- Support for Blender 3.0 has been added.
- Updates to the Render Quality modes:
    - RPR Interactive is a new mode supporting GPUs that use the Vulkan ray tracing extension, and is optimized for fast viewport rendering;
    - RPR Final, previously “Full” mode. It is intended for final rendering with the utmost physical correctness and image quality;  
    - Both modes produce similar images;
    - Both modes support full MaterialX shader networks.
- Support for ARM-based Apple Macs has been added.
- The ability to override the color of an object’s shadow has been added (in the visibility settings).

## Bugs Fixed:
- Blender objects using the “Fluid Modifier” were not rendering correctly — fixed.
- Outline rendering can now use UV mapping to generate the outline.
- Noise Threshold was previously locked in the viewport settings — fixed.
- The “Key Error 41” issue when exporting a .rpr file has been fixed.
- Incorrect Subsurface Scattering on Vega GPUS has been fixed.
- Black rendering of toon shaders on macOS has been fixed.
- A crash that could occur when processing emission shaders objects with subdivision added has been eliminated.
- The startup time for CPU rendering has been reduced.
- Low utilization on macOS with CPU + GPU rendering has been eliminated.
- Performance in scenes with many transparent materials has been improved.
- An issue with artifacts in alpha texture masks has been fixed.
- The render performance on Vega and Polaris GPUs has been improved.
- Particle motion blur on GPUs now works correctly.
- A bug in the “Monster Under the Bed” scene has been fixed.
- A crash that could occur when using .tif textures with zip compression has been eliminated.
- An issue with emission shaders disappearing in volume objects has been fixed.


# Version 3.3 
## New Features:
- Support for Fog and Heterogenous Volume rendering has been added to the RPR Full mode.  Simulated volumes are now rendered on CPU and GPU.  
- This includes support for the Blender Volume Scatter node and Principled Volume shader.

## Fixes:
- An output socket has been added in the Render Layer compositor node for Outline renders.
- An issue that could cause Material Previews not to work has been fixed.
- An error when Shadow Catcher objects were enabled with viewport rendering has been corrected.
- The following issues with Image Sequence texture not working have been fixed:
- Viewport and Final renders using texture sequences now look correct;
- Cyclic and Auto Refresh options in the image texture now work correctly;
- Support for numeric image filenames has been added.
- Hide/unhide could sometimes not work correctly with viewport rendering — fixed.
- Viewport upscaling now always uses 16-bit depth, which has fixed an issue with upscaling working on macOS.
- Emission Strength values > 1.0 now work correctly in the Principled Shader.
- Motion blur now works correctly with the “Center on Frame” and “Frame End” options.
- Setting the minimum samples option from 1 to 16 is now allowed (default is still 64).
- Hair rendering fixes:
    - Hair UVs now work correctly;
    - Textures are now supported for the color input of the Principled Hair BSDF and Hair BSDF;
    - The color and melanin settings of the Principled Hair BSDF now look more accurate.
    - Particle objects with hair on them were not rendering the hair — fixed.
- An issue with the “World” light being empty has been fixed.
- An AOV output “Camera Space Normal” has been added.
- Exporting .rpr files now takes into account material overrides.
- A warning is now added when an object with an excessive number of faces is exported.
- When a shader node was “muted,” that was not working in some cases — fixed.
- Differences in point lights between Cycles and ProRender have been mitigated.
- The Albedo AOV now passes the “Base color” on the Toon shader.
- A halo no longer appears around shadow and reflection catcher objects.
- AOVs passed through transparent or refractive materials — fixed.
- Noise convergence with emissive materials using textures has been improved.
- Performance with outline rendering has been improved.
- Performance regression on WX7100 GPUs has been fixed.
- The Object ID Lookup node now works in the Full mode.
- Objects with Toon shaders attached now cast shadows correctly if the flag is disabled.
- An issue detected on the latest NVidia drivers has been fixed.

## Known Issues:
- Volumes are not implemented on macOS.
- Vega GPUs with AMD 21.10 drivers can cause an issue when using the ML Denoiser.


# Version 3.2
## New Features:
- Subsurface Scattering and Volume shaders now work in RPR 2.0.  This allows the rendering of organic materials, such as skin, which absorb light into their interior.  Volume shaders can now also be used for simple fog boxes. Also the Volume Scatter node is supported. 
- Viewport denoising and upscaling improves the interactivity and speed of Viewport rendering.  With the use of the Radeon Image Filter Library, this allows Radeon ProRender to render at half resolution faster, and then upscale to the full size of the Viewport.
- Deformation motion blur gives accurate motion blur to objects which are being deformed, for example, a flag flapping in the wind or a ball squashing.  Besides, motion blur export has been optimized, and a setting for disabling deformation motion blur has been added.
- A new RPR Toon Shader has been added.  This enables cartoon-style shading for a non-photorealistic look.  Toon shaders can be used in a “simple” mode for just setting a color or a gradient of different colors for shadow vs lit areas of the object.
- Support for Blender 2.93 has been added.
- The look of “blocky” displacements has been significantly improved by enabling subdivision by default on objects with displacement shaders.  However, this does render slower, and can be overridden with the RPR Object Subdivision settings.
- Support has been added for Reflection Catcher and Transparent background in the Viewport in the Full mode.
- Outline rendering (formerly called Contour rendering) is now moved to the view layer AOV section. Outline rendering can be enabled just as the other AOVs.  The rendering process with Outline rendering enabled will take two passes per view layer, with the second doing the Outline rendering.
- Support for (Shutter) Position in the Motion Blur settings has been added.  This uses the cycles setting to control the shutter opening around the frame number.  
- Support for the Voronoi Texture node is added.

## Issues Fixed:
- Improve prop name readability in Object visibility UI. 
- Texture compression was causing artifacts in some scenes.  A “texture compression” setting has been added and defaulted to False.  You can enable this setting for faster renders, but make sure that there are no texture artifacts.
- The issue with the add-on not loading in versions of Blender downloaded from the Windows app store has been fixed.
- Objects set as Reflection Catchers now work in the Full mode.
- Overbright edges of objects with Uber shaders in metalness mode ― fixed.
- Shaders with high roughness could have artifacts with reflection or refraction ― fixed.
- Tiled rendering with a transparent background in the Full render quality has been fixed. 
- Occasional issues in starting the add-on in certain OSs have been fixed. 
- The option "Viewport Denoising and Upscaling" is saved to the scene settings.
- Memory leak in Viewport rendering with the Upscale filter enabled has been fixed.
- Image filters on Ubuntu20 have been fixed.
- Iterating all of view layers when baking all objects have been fixed.
- Fixed a crash in the viewport render if an object with hair and modifiers was not enabled for viewport display.
- Fixed an error with math nodes set to “Smooth min” or “Compare” modes.

## Known Issues:
- In RPR 2.0, heterogenous volumes, smoke and fire simulations or VDB files are not yet supported.
- Subsurface scattering and volume shader are currently disabled on macOS due to long compile times.
- Some AOVs may have artifacts on AMD cards with drivers earlier than 21.6.1


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
