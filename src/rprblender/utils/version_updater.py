"""
Update RPR data of older addon version for loaded scene.

Old RPR scenes used different internal data format. Blender loader is unable to map data to new structure so it
store it as "Custom Properties".
Module methods will look for old info in custom properties and map it to current variables.
"""

import bpy

from .logging import Log


log = Log(tag="VersionUpdater")


def is_scene_saved_by_older_addon_version(version):
    saved_version = tuple(bpy.context.scene.rpr.saved_addon_version)

    # ignore freshly created scenes and scene first time loaded with RPR
    if saved_version[0] == 0 and saved_version[1] == 0 and saved_version[2] == 0:
        return False

    if saved_version[0] >= version[0]:
        if saved_version[1] >= version[1]:
            if saved_version[2] >= version[2]:
                return False
    return True


def update_old_scene():
    update_environment()

    for obj in bpy.data.objects:
        update_object(obj)

    for entry in bpy.data.lights:
        update_light(entry)


def update_environment():
    """ Import environment lightning settings from world.rpr_data """
    world = bpy.context.scene.world
    env_data = world.get('rpr_data', None)
    if not env_data:
        return

    env_data = env_data.to_dict()
    environment = env_data.get('environment', None)
    if not environment:
        return

    env_enabled = environment.get('enable', True)
    world.rpr.enabled = env_enabled

    ibl = environment.get('ibl', None)
    if not ibl:
        return

    ibl_type = ibl.get('type', None)
    if ibl_type is not None:
        world.rpr.ibl_type = {0: 'COLOR', 1: 'IBL'}[ibl_type]

    # Environment light
    color = ibl.get('color', None)
    if color:
        world.rpr.ibl_color = color[:]

    ibl_image = ibl.get('ibl_image', None)
    if ibl_image:
        world.rpr.ibl_image = ibl_image

    intensity = ibl.get('intensity', None)
    if intensity is not None:
        world.rpr.ibl_intensity = intensity

    # Rotation Gizmo
    gizmo_object = environment.get('gizmo', None)
    if gizmo_object:
        world.rpr.gizmo = gizmo_object
    gizmo_rotation = environment.get('gizmo_rotation', None)
    if gizmo_rotation:
        world.rpr.gizmo_rotation = gizmo_rotation

    # TODO Import Environment Overrides
    # TODO Import Sun & Sky


def update_object(obj):
    """ Import data from obj.rpr_object """
    # Subdivision
    # Motion Blur
    # Visibility
    # Shadowcatcher
    # Portal light
    pass


def update_light(light):
    """ Import Physical lights data from light.rpr_lamp"""
    convert = (
        'intensity',
        'use_temperature',
        'temperature',
        'visible',
        'cast_shadows',
        # 'ies_file_name',
        'luminous_efficacy',
        'intensity_normalization',
        'shadow_softness',
    )

    if 'rpr_lamp' in light.keys():
        rpr_lamp = light['rpr_lamp']
        rpr_lamp = rpr_lamp.to_dict()

        for name in convert:
            value = rpr_lamp.get(name, None)
            if value is not None:
                setattr(light.rpr, name, value)

        color = rpr_lamp.get('color', None)
        if color:
            light.color = color[:]

        shape = rpr_lamp.get('shape', None)
        if shape is not None:
            light.rpr.shape = {0: 'SQUARE', 1: 'RECTANGLE', 2: 'DISK', 3: 'ELLIPSE', 4: 'MESH'}[shape]

        intensity_units_point = rpr_lamp.get('intensity_units_point', None)
        if intensity_units_point is not None:
            light.rpr.intensity_units_point =\
                {0: 'DEFAULT', 1: 'WATTS', 2: 'LUMEN'}[intensity_units_point]

        intensity_units_dir = rpr_lamp.get('intensity_units_dir', None)
        if intensity_units_dir is not None:
            light.rpr.intensity_units_dir =\
                {0: 'DEFAULT', 1: 'RADIANCE', 2: 'LUMINANCE'}[intensity_units_dir]

        intensity_units_area = rpr_lamp.get('intensity_units_area', None)
        if intensity_units_area is not None:
            light.rpr.intensity_units_area =\
                {0: 'DEFAULT', 1: 'WATTS', 2: 'LUMEN', 3: 'RADIANCE', 4: 'LUMINANCE'}[intensity_units_area]

        color_map = rpr_lamp.get('color_map', None)
        if color_map:
            light.rpr.color_map = color_map

        size1 = rpr_lamp.get('size_1', 0.1)
        size2 = rpr_lamp.get('size_2', 0.1)
        if light.type == 'AREA':
            if light.size == 0.0:
                light.size = size1
            if light.size_y == 0.0:
                light.size_y = size2

        group = rpr_lamp.get('group', 1)
        light.rpr.group = {0: 'KEY', 1: 'FILL'}[group]

        mesh_obj = rpr_lamp.get('mesh_obj', None)
        if mesh_obj is not None:
            if isinstance(mesh_obj, bpy.types.Mesh):
                light.rpr.mesh = mesh_obj
            elif isinstance(mesh_obj, bpy.types.Object):
                light.rpr.mesh = mesh_obj.data
