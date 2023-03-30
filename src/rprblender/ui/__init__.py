#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
import bpy


__all__ = ('RPR_Panel', 'register', 'unregister')


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
        'DATA_PT_context_light',
        'DATA_PT_falloff_curve',
        'DATA_PT_light',
        'NODE_DATA_PT_light',
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
    material_browser,
    view3d,
    mesh,
)


register_classes, unregister_classes = bpy.utils.register_classes_factory([
    render.RPR_RENDER_PT_devices,
    render.RPR_RENDER_PT_viewport_devices,
    render.RPR_RENDER_PT_quality,
    render.RPR_RENDER_PT_settings,
    render.RPR_RENDER_PT_limits,
    render.RPR_RENDER_PT_viewport_limits,
    render.RPR_RENDER_PT_advanced,
    render.RPR_RENDER_PT_pixel_filter,
    render.RPR_RENDER_PT_max_ray_depth,
    render.RPR_RENDER_PT_viewport_max_ray_depth,
    render.RPR_RENDER_PT_light_clamping,
    render.RPR_RENDER_PT_bake_textures,
    render.RPR_RENDER_PT_motion_blur,
    render.RPR_RENDER_PT_render_stamp,
    render.RPR_RENDER_PT_film_transparency,
    render.RPR_RENDER_PT_help_about,
    render.RPR_RENDER_PT_debug,

    object.RPR_OBJECT_PT_object,
    object.RPR_OBJECT_PT_visibility,
    object.RPR_OBJECT_PT_subdivision,

    light.RPR_LIGHT_PT_light,
    light.RPR_LIGHT_PT_intensity,

    material.RPR_MATERIAL_PT_context,
    material.RPR_MATERIAL_PT_preview,
    material.RPR_MATERIAL_PT_surface,
    material.RPR_MATERIAL_PT_displacement,
    material.RPR_MATERIAL_PT_volume,
    material_browser.RPR_MATERIL_PT_material_browser,
    material.RPR_MATERIAL_PT_node_arrange,
    material.RPR_MATERIAL_PT_node_bake,

    camera.RPR_CAMERA_PT_dof,
    camera.RPR_CAMERA_PT_dof_aperture,
    camera.RPR_CAMERA_PT_motion_blur,

    world.RPR_WORLD_PT_environment,
    world.RPR_WORLD_PT_sun_sky,
    world.RPR_WORLD_PT_gizmo,
    world.RPR_WORLD_PT_background_override,
    world.RPR_WORLD_PT_reflection_override,
    world.RPR_WORLD_PT_refraction_override,
    world.RPR_WORLD_PT_transparency_override,
    world.RPR_WORLD_PT_fog,
    world.RPR_WORLD_PT_atmosphere_volume,

    view_layer.RPR_VIEWLAYER_PT_aovs,
    view_layer.RPR_RENDER_PT_override,
    # view_layer.RPR_RENDER_PT_denoiser,
    view_layer.RPR_RENDER_PT_contour_rendering,

    view3d.RPR_VIEW3D_MT_menu,
    view3d.RPR_VIEW3D_PT_panel,
    view3d.RPR_VIEW3D_PT_shading_lighting,
    view3d.RPR_VIEW3D_PT_shading_render_pass,

    mesh.RPR_DATA_PT_mesh,
])


def register():
    # set rpr panels filter
    for panel in get_panels():
        panel.COMPAT_ENGINES.add('RPR')

    register_classes()

    # adding draw_menu function to viewport menu class
    bpy.types.VIEW3D_MT_editor_menus.append(view3d.draw_menu)


def unregister():
    # remove rpr panels filter
    for panel in get_panels():
        if 'RPR' in panel.COMPAT_ENGINES:
            panel.COMPAT_ENGINES.remove('RPR')

    unregister_classes()

    # removing draw_menu function from viewport menu class
    bpy.types.VIEW3D_MT_editor_menus.remove(view3d.draw_menu)
