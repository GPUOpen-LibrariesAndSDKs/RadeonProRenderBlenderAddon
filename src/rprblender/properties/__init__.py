import bpy

from rprblender import logging

from . import (
    Render,
    Object,
    Mesh,
    Light,
    Material,
)


modules_to_register = (
    Render,
    Object,
    Mesh,
    Light,
    Material,
)


# Register/unregister all required classes of RPR properties in one go
classes = []
for module in modules_to_register:
    module_classes = getattr(module, "classes", None)
    if module_classes:
        classes.extend(module_classes)
logging.debug("Classes to register are {}".format(classes), tag="properties")
register_classes, unregister_classes = bpy.utils.register_classes_factory(classes)


# Extend Blender panels to work with RPR
def get_panels():
    # follow the Cycles model of excluding panels we don't want

    exclude_panels = {
        'DATA_PT_area',
        'DATA_PT_camera_dof',
        'DATA_PT_context_light',
        'DATA_PT_falloff_curve',
        'DATA_PT_light',
        'DATA_PT_preview',
        'DATA_PT_shadow',
        'DATA_PT_spot',
        'DATA_PT_sunsky',
        'MATERIAL_PT_context_material',
        'MATERIAL_PT_diffuse',
        'MATERIAL_PT_flare',
        'MATERIAL_PT_halo',
        'MATERIAL_PT_mirror',
        'MATERIAL_PT_options',
        'MATERIAL_PT_pipeline',
        'MATERIAL_PT_preview',
        'MATERIAL_PT_shading',
        'MATERIAL_PT_shadow',
        'MATERIAL_PT_specular',
        'MATERIAL_PT_sss',
        'MATERIAL_PT_strand',
        'MATERIAL_PT_transp',
        'MATERIAL_PT_volume_density',
        'MATERIAL_PT_volume_integration',
        'MATERIAL_PT_volume_lighting',
        'MATERIAL_PT_volume_options',
        'MATERIAL_PT_volume_shading',
        'MATERIAL_PT_volume_transp',
        'RENDERLAYER_PT_layer_options',
        'RENDERLAYER_PT_layer_passes',
        'RENDERLAYER_PT_views',
        'RENDER_PT_antialiasing',
        'RENDER_PT_bake',
        'RENDER_PT_motion_blur',
        'RENDER_PT_performance',
        'RENDER_PT_freestyle',
        'RENDER_PT_post_processing',
        'RENDER_PT_shading',
        'RENDER_PT_stamp',
        'SCENE_PT_simplify',
        'SCENE_PT_audio',
        'WORLD_PT_ambient_occlusion',
        'WORLD_PT_environment_lighting',
        'WORLD_PT_gather',
        'WORLD_PT_indirect_lighting',
        'WORLD_PT_mist',
        'WORLD_PT_preview',
        'WORLD_PT_world',
    }

    panels = []
    for t in bpy.types.Panel.__subclasses__():
        if hasattr(t, 'COMPAT_ENGINES') and 'BLENDER_RENDER' in t.COMPAT_ENGINES:
            if t.__name__ not in exclude_panels:
                panels.append(t)

    return panels


def register():
    for panel in get_panels():
        panel.COMPAT_ENGINES.add('RPR')

    register_classes()


def unregister():
    for panel in get_panels():
        if 'RPR' in panel.COMPAT_ENGINES:
            panel.COMPAT_ENGINES.remove('RPR')

    unregister_classes()
