import bpy

__all__ = ('RPR_Panel', 'register', 'unregister', 'set_rpr_panels_filter', 'remove_rpr_panels_filter')

PANEL_WIDTH_FOR_COLUMN = 200


class RPR_Panel(bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'render'
    COMPAT_ENGINES = {'RPR'}

    @classmethod
    def poll(cls, context):
        return context.engine in cls.COMPAT_ENGINES

    @staticmethod
    def create_ui_autosize_column(context, column, single=False):
        if context.region.width > PANEL_WIDTH_FOR_COLUMN:
            row = column.row()
            split = row.split(factor=0.5)
            column1 = split.column(align=True)
            split = split.split()
            column2 = split.column(align=True)
            is_row = False
        else:
            column1 = column.row().column(align=True)
            if not single:
                column.separator()
            column2 = column.row().column(align=True)
            is_row = True
        return column1, column2, is_row


def get_panels():
    # follow the Cycles model of excluding panels we don't want

    exclude_panels = {
        'DATA_PT_area',
        'DATA_PT_camera_dof',
        'DATA_PT_context_light',
        'DATA_PT_falloff_curve',
        'DATA_PT_light',
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


from . import (
    render,
    object,
    light,
    material,
    camera,
    world,
    view_layer,
)

register, unregister = bpy.utils.register_classes_factory([
    render.RPR_RENDER_PT_devices,
    render.RPR_RENDER_PT_limits,
    render.RPR_RENDER_PT_viewport_limits,
    render.RPR_RENDER_PT_quality,
    render.RPR_RENDER_PT_max_ray_depth,
    render.RPR_RENDER_PT_light_clamping,
    render.RPR_RENDER_PT_effects,
    render.RPR_RENDER_PT_help_about,

    object.RPR_OBJECT_PT_object,
    object.RPR_OBJECT_PT_motion_blur,

    light.RPR_LIGHT_PT_light,

    material.RPR_MATERIAL_PT_context,
    material.RPR_MATERIAL_PT_preview,
    material.RPR_MATERIAL_PT_surface,

    camera.RPR_CAMERA_PT_motion_blur,

    world.RPR_WORLD_PT_environment,

    view_layer.RPR_VIEWLAYER_PT_aovs,
    view_layer.RPR_RENDER_PT_denoiser,
])


def set_rpr_panels_filter():
    for panel in get_panels():
        panel.COMPAT_ENGINES.add('RPR')


def remove_rpr_panels_filter():
    for panel in get_panels():
        if 'RPR' in panel.COMPAT_ENGINES:
            panel.COMPAT_ENGINES.remove('RPR')
