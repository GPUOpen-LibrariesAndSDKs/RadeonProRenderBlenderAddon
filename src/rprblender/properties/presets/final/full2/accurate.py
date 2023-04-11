import bpy

rpr = bpy.context.scene.rpr

rpr.ray_depth.max_ray_depth = 14
rpr.ray_depth.diffuse_depth = 9
rpr.ray_depth.glossy_depth = 12
rpr.ray_depth.shadow_depth = 8
rpr.ray_depth.refraction_depth = 14
rpr.ray_depth.glossy_refraction_depth = 11

rpr.limits.min_samples = 64
rpr.limits.max_samples = 128
