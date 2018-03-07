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


def is_blender_support_ibl_image():
    return bpy.app.version >= BLENDER_SUPPORTED_CUSTOM_DATABLOCK


def is_older_than_version(version1, version2):
    if version1[0] == version2[0]:
        if version1[1] == version2[1]:
            if version1[2] != version2[2]:
                return version1[2] < version2[2]
        else:
            return version1[1] < version2[1]
    else:
        return version1[0] < version2[0]

    return False

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
    if not is_blender_support_aov():
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


def get_render_passes_aov_list(context, is_preview):
    if is_preview:
        return ([("", bpy.context.scene.rpr.preview_aov)], 0)

    if is_blender_support_aov():
        return ([(layer.name, layer.rpr_data.passes_aov) for layer in context.scene.render.layers], context.scene.render.layers.active_index)
    else:
        return ([("", context.scene.rpr.render.passes_aov)], 0)


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

            if node.displacement_min not in node.inputs:
                socket = node.inputs.new('rpr_socket_float_softMin0_softMax1', node.displacement_min)
                socket.default_value = 0.0
                socket.enabled = node.displacement

            if node.displacement_max not in node.inputs:
                socket = node.inputs.new('rpr_socket_float_softMin0_softMax1', node.displacement_max)
                socket.default_value = 1.0
                socket.enabled = node.displacement


# convert old RPR Environment settings image paths to image datablock references
def check_old_rpr_ibl_images():
    # skip check for newest saved settings version
    if is_newer_than_saved_addon_version((1, 2, 5)):
        return

    logging.debug("check_old_rpr_ibl_images", tag="version.upgrade.environment")
    if not is_blender_support_ibl_image():
        return

    logging.debug("bpy.data.worlds:", len(bpy.data.worlds), tag="version.upgrade.environment")
    for world in bpy.data.worlds:
        environment = world.rpr_data and world.rpr_data.environment  # type: rprblender.properties.RenderEnvironment
        if not environment:
            continue

        fpath = environment.ibl.get('ibl_map', None)
        if fpath:
            # fpath_normalized = bpy.path.native_pathsep(bpy.path.abspath(fpath))
            # found = False
            # for image_name, image in bpy.data.images.items():
            #     if fpath_normalized == bpy.path.native_pathsep(bpy.path.abspath(image.filepath_raw)):
            #         logging.info("Converting ibl ot use image ", image_name, tag="version.upgrade.environment")
            #         environment.ibl.image = image
            #         del environment.ibl['ibl_map']
            #         found = True
            # if not found:
            image = load_image(fpath)
            logging.info("Setting ibl image on", world.name, "from", fpath, "to", image, tag="version.upgrade.environment")
            environment.ibl.ibl_image = image
            del environment.ibl['ibl_map']

        fpath = environment.ibl.maps.get('background_map', None)
        if fpath:
            image = load_image(fpath)
            logging.info("Setting background image on ", world.name, "from", fpath, "to", image, tag="version.upgrade.environment")
            environment.ibl.maps.background_image = image
            del environment.ibl.maps['background_map']


def load_image(fpath):
    try:
        image = bpy.data.images.load(fpath, True)
    except RuntimeError as e:
        logging.info("Coudn't load image for ", fpath, ", reason: ", e, tag="version.upgrade.environment")
        image = bpy.data.images.new(fpath, width=1, height=1, float_buffer=True)
        image.pixels = [1, 0, 1, 1]
        image.filepath = fpath
    return image

