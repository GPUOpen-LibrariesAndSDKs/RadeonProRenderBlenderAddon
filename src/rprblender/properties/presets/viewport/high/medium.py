import bpy

rpr = bpy.context.scene.rpr

rpr.viewport_ray_depth.max_ray_depth = 9
rpr.viewport_ray_depth.diffuse_depth = 7
rpr.viewport_ray_depth.glossy_depth = 8
rpr.viewport_ray_depth.shadow_depth = 5
rpr.viewport_ray_depth.refraction_depth = 9
rpr.viewport_ray_depth.glossy_refraction_depth = 7

rpr.viewport_limits.min_samples = 32
rpr.viewport_limits.max_samples = 64
