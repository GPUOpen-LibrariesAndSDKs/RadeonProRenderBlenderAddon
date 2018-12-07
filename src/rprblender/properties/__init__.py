''' property classes should be self contained.  They may include:
    PropertyGroup class
        with properties that can be attached to a blender ID type
        methods for syncing these properties
    And panel classes for displaying these properties

    The idea here is to keep all the properties syncing, data, display etc in one place.
    Basically a "model/view" type pattern where we bring them together for ease of maintenance.
    Slightly inspired by vue.js

    TODO could we use decorators to register???
'''

import bpy
from rprblender import logging


class RPR_Properties(bpy.types.PropertyGroup):
    def sync(self, context):
        ''' Sync will update this object in the context.
            And call any sub-objects that need to be synced
            rpr_context object in the binding will be the only place we keep
        "lists of items synced." '''
        pass


class RPR_Panel(bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'render'
    COMPAT_ENGINES = {'RPR'}

    @classmethod
    def poll(cls, context):
        return context.engine in cls.COMPAT_ENGINES


# Register/unregister all required classes of RPR properties in one go
from . import (
    Render,
    Mesh,
    Object,
    Light,
    Camera,
    Material,
)

modules_to_register = (
    Render,
    Mesh,
    Object,
    Light,
    Camera,
    Material,
)

classes_to_register = []
for module in modules_to_register:
    module_classes = getattr(module, 'classes_to_register', None)
    if module_classes:
        classes_to_register.extend(module_classes)

logging.debug("Classes to register are {}".format(classes_to_register), tag="properties")
register_classes, unregister_classes = bpy.utils.register_classes_factory(classes_to_register)


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
        'RENDER_PT_simplify',
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
