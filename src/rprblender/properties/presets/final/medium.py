import bpy

rpr = bpy.context.scene.rpr

rpr.ray_depth.max_ray_depth = 16
rpr.ray_depth.diffuse_depth = 16
rpr.ray_depth.glossy_depth = 16
rpr.ray_depth.shadow_depth = 16
rpr.ray_depth.refraction_depth = 16
rpr.ray_depth.glossy_refraction_depth = 16

rpr.limits.min_samples = 32
rpr.limits.max_samples = 64
