#!python3
import bpy
import math
import sys
import addon_utils

import rprblender
from . import logging

BLENDER_SUPPORTED_AOV = (2, 78, 5)
BLENDER_SUPPORTED_CUSTOM_DATABLOCK = (2, 78, 5)


def is_blender_support_aov():
    return bpy.app.version >= BLENDER_SUPPORTED_AOV


def is_blender_support_new_image_node():
    return bpy.app.version >= BLENDER_SUPPORTED_CUSTOM_DATABLOCK


def is_blender_support_ibl_image():
    return bpy.app.version >= BLENDER_SUPPORTED_CUSTOM_DATABLOCK


def is_blender_support_custom_datablock():
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


def get_core_version():
    from pyrpr import API_VERSION
    return API_VERSION


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


def check_old_rpr_uber2_nodes(update, convert):
    for mat in bpy.data.materials:
        tree = mat.node_tree
        if not tree:
            continue

        material_editor = rprblender.material_editor.MaterialEditor(tree)

        for node in mat.node_tree.nodes:
            if node.bl_idname != 'rpr_shader_node_uber2':
                continue

            if update:
                # add all missing sockets for older Uber2 versions
                node.add_socket_if_missed(node.reflection_fresnel_ior, 'rpr_socket_ior',
                                          default_value=1.5, enabled=node.reflection)
                node.add_socket_if_missed(node.reflection_fresnel_metalness, 'rpr_socket_weight',
                                          default_value=1.0, enabled=node.reflection)

                node.add_socket_if_missed(node.refraction_roughness, 'rpr_socket_weight',
                                          default_value=0.1, enabled=node.refraction)

                node.add_socket_if_missed(node.subsurface_color, 'rpr_socket_color',
                                          default_value=(1.0, 1.0, 1.0, 1.0), enabled=node.subsurface)
                node.add_socket_if_missed(node.subsurface_weight, 'rpr_socket_weight_soft',
                                          default_value=1.0, enabled=node.subsurface)
                node.add_socket_if_missed(node.subsurface_scatter_color, 'rpr_socket_color',
                                          default_value=(3.67, 1.37, 0.68, 1.0), enabled=node.subsurface)
                node.add_socket_if_missed(node.subsurface_scatter_direction, 'rpr_socket_scattering_direction',
                                          default_value=0.0, enabled=node.subsurface)
                node.add_socket_if_missed(node.subsurface_radius, 'rpr_socket_color',
                                          default_value=(1.0, 1.0, 1.0, 1.0), enabled=node.subsurface)

                node.add_socket_if_missed(node.coating_fresnel_ior, 'rpr_socket_ior',
                                          default_value=1.5, enabled=node.coating)

                node.add_socket_if_missed(node.emissive_intensity, 'rpr_socket_factor',
                                          enabled=node.emissive)

                node.add_socket_if_missed(node.displacement_min, 'rpr_socket_float_softMinN1_softMax1',
                                          default_value=0.0, enabled=node.displacement)
                node.add_socket_if_missed(node.displacement_max, 'rpr_socket_float_softMinN1_softMax1',
                                          default_value=1.0, enabled=node.displacement)

                node.add_socket_if_missed(node.normal_in, 'rpr_socket_link', enabled=node.normal)

                node.total_update(None)

            if convert:
                # convert to the state-of-art Uber3 material
                replacement = material_editor.create_uber_material_node3()
                convert_uber2_to_uber3(source_node=node, tree=tree, replacement_node=replacement)


class SocketConversionInfo:
    """Storage structure for socket conversion info"""
    def __init__(self, source_name, destination_name, translate_rules=None, update_method=""):
        self.source_name = source_name
        self.destination_name = destination_name
        self.translate_rules = translate_rules
        self.update_method = update_method


uber2_to_uber3 = {
    "sections":
        (
            "diffuse", "reflection", "refraction", "coating", "emissive", "subsurface",
            "transparency", "normal", "displacement"
        ),

    "ui_to_ui":
        (
            SocketConversionInfo("reflection_fresnel_metalmaterial", "reflection_mode",
                                 translate_rules=lambda v: {False: "IOR", True: "METALNESS"}[v],
                                 update_method="reflection_mode_changed"),
            SocketConversionInfo("refraction_thin_surface", "refraction_thin_surface",),
            SocketConversionInfo("emissive_double_sided", "emissive_double_sided", ),
            SocketConversionInfo("subsurface_use_diffuse_color", "subsurface_use_diffuse_color",
                                 update_method="subsurface_use_diffuse_color_changed"),
            SocketConversionInfo("subsurface_multiple_scattering", "subsurface_multiple_scattering", ),
        ),

    "input_to_input":
        (
            SocketConversionInfo("diffuse_color", "diffuse_color",),
            SocketConversionInfo("diffuse_weight", "diffuse_weight",),
            SocketConversionInfo("diffuse_roughness", "diffuse_roughness",),

            SocketConversionInfo("reflection_color", "reflection_color",),
            SocketConversionInfo("reflection_weight", "reflection_weight",),
            SocketConversionInfo("reflection_roughness", "reflection_roughness",),
            SocketConversionInfo("reflection_anisotropy", "reflection_anisotropy",),
            SocketConversionInfo("reflection_anisotropy_rotation", "reflection_anisotropy_rotation",),
            SocketConversionInfo("reflection_fresnel_ior", "reflection_ior",),
            SocketConversionInfo("reflection_fresnel_metalness", "reflection_metalness",),

            SocketConversionInfo("refraction_color", "refraction_color",),
            SocketConversionInfo("refraction_weight", "refraction_weight",),
            SocketConversionInfo("refraction_roughness", "refraction_roughness",),
            SocketConversionInfo("refraction_ior", "refraction_ior",),

            SocketConversionInfo("coating_color", "coating_color",),
            SocketConversionInfo("coating_weight", "coating_weight",),
            SocketConversionInfo("coating_roughness", "coating_roughness",),
            SocketConversionInfo("coating_fresnel_ior", "coating_ior",),

            SocketConversionInfo("emissive_color", "emissive_color",),
            SocketConversionInfo("emissive_weight", "emissive_weight",),

            SocketConversionInfo("subsurface_weight", "subsurface_weight",),
            SocketConversionInfo("subsurface_scatter_color", "subsurface_scatter_color",),
            SocketConversionInfo("subsurface_scatter_direction", "subsurface_scatter_direction",),
            SocketConversionInfo("subsurface_radius", "subsurface_radius",
                                 translate_rules=lambda v: v[0:3]),

            SocketConversionInfo("transparency_value", "transparency_value",),
            SocketConversionInfo("normal_in", "normal_in",),
            SocketConversionInfo("displacement_map", "displacement_map",),
        ),

    "input_to_ui":
        (
            SocketConversionInfo("emissive_intensity", "emissive_intensity",
                                 translate_rules=lambda v: min(1.0, max(0.0, v))),
            SocketConversionInfo("displacement_min", "",
                                 translate_rules=lambda v: max(0.0, v)),
            SocketConversionInfo("displacement_max", "",
                                 translate_rules=lambda v: max(0.0, v)),
        ),
}


def convert_uber2_to_uber3(source_node, tree, replacement_node):
    def get_input_socket(node, name):
        result = None
        internal_name = name
        if hasattr(node, name):
            internal_name = getattr(node, name)
            if internal_name in node.inputs:
                result = node.inputs[internal_name]
        if not result:
            logging.debug("Converting Uber2 to Uber3[{}]: unable to find input socket '{}'.".
                          format(node.bl_idname, internal_name))
        return result

    # enable material node sections first
    for name in uber2_to_uber3['sections']:
        state = getattr(source_node, name)
        setattr(replacement_node.node, name, state)
        replacement_node.node.total_update()

    # UI fields to UI fields
    for entry in uber2_to_uber3['ui_to_ui']:
        value = getattr(source_node, entry.source_name)
        if entry.translate_rules:
            value = entry.translate_rules(value)
        setattr(replacement_node.node, entry.destination_name, value)

        if entry.update_method:
            if hasattr(replacement_node.node, entry.update_method):
                getattr(replacement_node.node, entry.update_method)(None)
            else:
                logging.warn("Unable to find update method '{}'".format(entry.update_method))

    # Input sockets to input sockets
    for entry in uber2_to_uber3['input_to_input']:
        source_input = get_input_socket(source_node, entry.source_name)
        if not source_input:
            continue

        replacement_input = get_input_socket(replacement_node.node, entry.destination_name)
        if not replacement_input:
            continue

        if source_input.is_linked:
            for link in source_input.links:
                tree.links.new(link.from_socket, replacement_input)
        else:
            value = source_input.default_value
            if entry.translate_rules:
                value = entry.translate_rules(value)
            replacement_input.default_value = value

    # Input sockets to UI fields
    for entry in uber2_to_uber3['input_to_ui']:
        source_input = get_input_socket(source_node, entry.source_name)
        if not source_input:
            continue
        if source_input.is_linked:  # could not link UI field
            continue

        value = source_input.default_value
        if entry.translate_rules:
            value = entry.translate_rules(value)
        setattr(replacement_node.node, entry.destination_name, value)

        if entry.update_method:
            if hasattr(replacement_node.node, entry.update_method):
                getattr(replacement_node.node, entry.update_method)(None)
            else:
                logging.warn("Unable to find update method '{}'".format(entry.update_method))

    # Time to replace the output links of the source
    new_output = replacement_node.node.outputs[replacement_node.node.shader_out]
    if source_node.outputs and len(source_node.outputs) == 1 and source_node.outputs[0].is_linked:
        for link in source_node.outputs[0].links:
            tree.links.new(new_output, link.to_socket)

        replacement_node.node.location = source_node.location[:]

    logging.debug("Material node {} updated from Uber2 to Uber3, new node {}".format(source_node, replacement_node))

    tree.nodes.remove(source_node)


def check_old_rpr_uber3_nodes():
    for mat in bpy.data.materials:
        tree = mat.node_tree

        if not tree:
            continue

        for node in mat.node_tree.nodes:
            if node.bl_idname != 'rpr_shader_node_uber3':
                continue

            node.add_socket_if_missed(node.refraction_absorption_color, 'rpr_socket_color',
                                      (1.0, 1.0, 1.0, 1.0), node.refraction)
            node.add_socket_if_missed(node.refraction_normal, 'rpr_socket_link',
                                      enabled=not node.refraction_use_shader_normal, hide_value=True)
            node.add_socket_if_missed(node.sheen_color, 'rpr_socket_color', (0.5, 0.5, 0.5, 1.0), node.sheen)
            node.add_socket_if_missed(node.sheen_weight, 'rpr_socket_weight_soft', 1.0, node.sheen) 
            node.add_socket_if_missed(node.sheen_tint, 'rpr_socket_weight', 0.5, node.sheen)


def check_old_mapping_nodes():
    for mat in bpy.data.materials:
        tree = mat.node_tree

        if not tree:
            continue

        for node in mat.node_tree.nodes:
            if node.bl_idname != 'rpr_mapping_node':
                continue

            node.add_socket_if_missed(node.angle_in, 'rpr_socket_float',
                                      0.0, True)


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

