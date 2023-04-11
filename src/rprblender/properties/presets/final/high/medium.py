import bpy

rpr = bpy.context.scene.rpr

rpr.ray_depth.max_ray_depth = 9
rpr.ray_depth.diffuse_depth = 7
rpr.ray_depth.glossy_depth = 8
rpr.ray_depth.shadow_depth = 5
rpr.ray_depth.refraction_depth = 9
rpr.ray_depth.glossy_refraction_depth = 7

rpr.limits.min_samples = 32
rpr.limits.max_samples = 64
