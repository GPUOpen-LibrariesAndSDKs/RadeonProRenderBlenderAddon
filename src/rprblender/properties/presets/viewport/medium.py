import bpy

rpr = bpy.context.scene.rpr

rpr.viewport_ray_depth.max_ray_depth = 16
rpr.viewport_ray_depth.diffuse_depth = 16
rpr.viewport_ray_depth.glossy_depth = 16
rpr.viewport_ray_depth.shadow_depth = 16
rpr.viewport_ray_depth.refraction_depth = 16
rpr.viewport_ray_depth.glossy_refraction_depth = 16

rpr.viewport_limits.min_samples = 32
rpr.viewport_limits.max_samples = 64

rpr.viewport_upscale_quality = 'FSR2_QUALITY_MODE_BALANCE'
