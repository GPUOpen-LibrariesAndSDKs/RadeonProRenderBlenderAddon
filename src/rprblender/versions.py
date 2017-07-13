#!python3
import bpy
import math
import sys
import addon_utils
from . import logging


BLENDER_SUPPORTED_AOV = (2, 78, 5)
BLENDER_SUPPORTED_CUSTOM_DATABLOCK = (2, 78, 5)

def is_blender_support_aov():
    return bpy.app.version >= BLENDER_SUPPORTED_AOV


def is_blender_support_new_image_node():
    return bpy.app.version >= BLENDER_SUPPORTED_CUSTOM_DATABLOCK


def is_newer_than_saved_addon_version(version):
    if bpy.context.scene.rpr.saved_addon_version[0] >= version[0]:
        if bpy.context.scene.rpr.saved_addon_version[1] >= version[1]:
            if bpy.context.scene.rpr.saved_addon_version[2] >= version[2]:
                return True
    return False


def get_addon_info():
    mod = sys.modules.get(__package__)
    return addon_utils.module_bl_info(mod)


def get_addon_version():
    info = get_addon_info()
    return info['version']


def copy_settings(src, dst, keys):
    for key, value in keys.items():
        settings_value = src.get(key, value)
        if type(value) != dict:
            dst[key] = settings_value
        else:
            a = getattr(dst, key)
            copy_settings(settings_value, a, value)


# convert old scenes (AMDBLENDER-653)
def check_old_environment_settings():
    try:
        if bpy.context.scene.rpr.render['environment'] is None:
            return
    except KeyError:
        return

    logging.info('Copy old environment settings to world...')

    keys = {
        'enable': True,
        'rotation': (0,0,0),
        'type': 0,
        'ibl': {
            'color': (0.5, 0.5, 0.5),
            'intensity': 1.0,
            'use_ibl_map': False,
            'ibl_map': '',
            'maps': {
                'override_background': False,
                'override_background_type': 'image',
                'background_map': '',
                'background_color': (0.5, 0.5, 0.5),
            }
        },
        'sun_sky': {
            'type': 'analytical_sky',
            'azimuth': 0,
            'altitude': math.radians(30),
            'latitude': math.radians(38),
            'longitude': math.radians(27),
            'date_year': 2016,
            'date_month': 1,
            'date_day': 1,
            'time_hours': 12,
            'time_minutes': 0,
            'time_seconds': 0,
            'time_zone': 0,
            'daylight_savings': True,
            'turbidity': 0.2,
            'intensity': 1.0,
            'sun_glow': 1.0,
            'sun_disc': 0.5,
            'saturation': 0.5,
            'horizon_height': 0.001,
            'horizon_blur': 0.1,
            'filter_color': (0.0, 0.0, 0.0),
            'ground_color': (0.4, 0.4, 0.4),
            'texture_resolution': 'normal',
        }
    }

    copy_settings(bpy.context.scene.rpr.render['environment'], bpy.context.scene.world.rpr_data.environment, keys)
    del bpy.context.scene.rpr.render['environment']
    logging.info('copy ok.')



# convert old scenes (AMDBLENDER-652)
def check_old_passes_aov_settings():
    if not is_blender_support_aov:
        return

    try:
        if bpy.context.scene.rpr.render['passes_aov'] is None:
            return
    except KeyError:
        return

    logging.info('Copy old passes_aov settings to layers...')

    from rprblender.properties import RenderPassesAov

    arr = (False, False, False, False, False, False, False, False)
    assert len(arr) == len(RenderPassesAov.render_passes_items)

    keys = {
        'enable': False,
        'pass_displayed': 'default',
        'passesStates': arr,
        'transparent': False,
    }

    copy_settings(bpy.context.scene.rpr.render['passes_aov'], bpy.context.scene.render.layers.active.rpr_data.passes_aov, keys)
    del bpy.context.scene.rpr.render['passes_aov']
    logging.info('copy ok.')


def dump_scene_addon_version():
    version = bpy.context.scene.rpr.saved_addon_version
    if not version[0]:
        logging.info("File was saved by unknown addon version")
    else:
        logging.info("File was saved by addon v%d.%d.%d" % (version[0], version[1], version[2]))


def set_scene_addon_version():
    bpy.context.scene.rpr.saved_addon_version = get_addon_version()


def get_render_passes_aov(context):
    if is_blender_support_aov():
        return context.scene.render.layers.active.rpr_data.passes_aov
    else:
        return context.scene.rpr.render.passes_aov


# convert old RPR Image nodes (AMDBLENDER-696)
def check_old_rpr_image_nodes():
    if not is_blender_support_new_image_node():
        return

    for mat in bpy.data.materials:
        tree = mat.node_tree
        if not tree:
            continue

        for node in mat.node_tree.nodes:
            if node.bl_idname != 'rpr_texture_node_image_map':
                continue

            try:
                name = node['image_name']
                if name:
                    logging.info("Found old image: ", name)
                    node.image = bpy.data.images[name]
                    del node['image_name']
            except KeyError:
                continue



def check_old_rpr_uber2_nodes():
    if is_newer_than_saved_addon_version((1,2,4)):
        return

    for mat in bpy.data.materials:
        tree = mat.node_tree
        if not tree:
            continue

        for node in mat.node_tree.nodes:
            if node.bl_idname != 'rpr_shader_node_uber2':
                continue

            if node.emissive_intensity not in node.inputs:
                socket = node.inputs.new('rpr_socket_factor', node.emissive_intensity)
                socket.enabled = node.emissive

            if node.normal_in not in node.inputs:
                socket = node.inputs.new('rpr_socket_link', node.normal_in)
                socket.enabled = node.normal
