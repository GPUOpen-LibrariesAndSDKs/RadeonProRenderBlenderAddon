#!python3

bl_info = {
    "name": "Radeon ProRender",
    "description": "Radeon ProRender rendering plugin for Blender.",
    "author": "AMD",
    "version": (1, 6, 170),
    "blender": (2, 78, 0),
    "location": "Info header, render engine menu",
    "warning": "",  # used for warning icon and text in addons panel
    "wiki_url": "https://radeon-prorender.github.io",
    "tracker_url": "https://firerender.freshdesk.com/support/discussions",
    "category": "Render"
}

import bpy
import sys

from . import logging
logging.info("Loading RPR addon", bl_info['version']);

from . import config
from . import addon
from . import versions


class Addon(addon.Addon):
    pass


rpraddon = Addon()


def check_data_from_library():
    if versions.is_blender_support_new_image_node():
        return
    for mat in bpy.data.materials:
        lib = mat.library
        if not lib:
            continue

        tree = mat.node_tree
        if not tree:
            continue
        for node in mat.node_tree.nodes:
            if node.bl_idname == 'rpr_texture_node_image_map':
                if node.image_name in bpy.data.images:
                    continue

                logging.info('add image: ', node.image_name)
                with bpy.data.libraries.load(lib.filepath, link=True) as (data_from, data_to):
                    if node.image_name in data_from.images:
                        data_to.images.append(node.image_name)


# handlers
# https://www.blender.org/api/blender_python_api_2_77_3/bpy.app.handlers.html
@bpy.app.handlers.persistent
def load_post(dummy):
    logging.info("load_post...")
    versions.dump_scene_addon_version()

    from . import nodes
    nodes.node_groups_load_post()

    from . import node_thumbnail
    node_thumbnail.unregister()

    if config.preview_enable:
        init_preview_data()

    from . import helpers

    if __package__ not in bpy.context.user_preferences.addons.keys():
        helpers.render_resources_helper.init_gpu_states()

    helpers.render_resources_helper.enable_autosave()


    if bpy.context.scene.world:
        versions.check_old_environment_settings()
        bpy.context.scene.world.rpr_data.environment.switch_sun_helper()


    versions.check_old_passes_aov_settings()

    versions.check_old_rpr_image_nodes()
    versions.check_old_rpr_uber2_nodes()
    versions.check_old_rpr_ibl_images()

    check_data_from_library()

    from rprblender import render

    # free cached render device to make sure cached images don't consume memory
    # as RPR doesn't free images created from files, see AMDBLENDER-789
    render.free_render_devices()

    logging.debug("load_post ok")


def init_preview_data():
    from . import sync
    sync.SceneSynced.create_preview_mesh()
    from rprblender.render import engine
    engine.RPREngine.init_preview_settings()


prev_engine = ''
prev_nodeeditor_name = ''


@bpy.app.handlers.persistent
def on_scene_update_post(scene):
    if bpy.data.libraries.is_updated:
        check_data_from_library()

    global prev_engine, prev_nodeeditor_name
    # TODO: here we might collect information on what was updated in the scene
    # for regular render(non-viewport which has its view_update) to optimize scene export -
    # make it iterative and not to re-export the whole scene every F12
    # print('on_scene_update_post', scene)
    try:
        from . import ui
    except:
        print("import ui failed")
        # TN: Any issues with DLLs seem to show up here.  Uncomment for a quick
        # exit while debugging
        # sys.exit(0)

    # switch space.tree_type when we changed render engine
    if prev_engine != scene.render.engine and scene.render.engine == 'RPR':
        if not ui.activate_editor(prev_nodeeditor_name):
            ui.activate_shader_editor()

    prev_engine = scene.render.engine
    prev_nodeeditor_name = ui.get_activate_editor_name()

    # update gizmo rotation
    if hasattr(bpy.context.scene.world, 'rpr_data'):
        env = bpy.context.scene.world.rpr_data.environment
        if bpy.data.objects.is_updated:
            name = env.gizmo
            if name in bpy.data.objects:
                obj = bpy.data.objects[name]
                if obj.is_updated:
                    env['gizmo_rotation'] = obj.rotation_euler


bpy.app.handlers.scene_update_post.append(on_scene_update_post)


# this can be had on scene load, not persistent
@bpy.app.handlers.persistent
def frame_change_pre(scene):
    logging.debug("frame_change_pre", scene.frame_current)


@bpy.app.handlers.persistent
def save_pre(dummy):
    logging.debug("save_pre...")
    versions.set_scene_addon_version()


bpy.app.handlers.frame_change_pre.append(frame_change_pre)
bpy.app.handlers.save_pre.append(save_pre)


def register():
    logging.info('rpr.register')
    logging.info('Blender version: ', bpy.app.version)

    bpy.app.handlers.load_post.append(load_post)

    from . import render  # import render first to initialize pyrpr(can be used in other modules)
    from rprblender.render import engine

    # Attention! Calls order is important
    from . import helpers
    logging.info("helpers.register()")
    helpers.register()
    from . import properties
    properties.register()

    if __package__ in bpy.context.user_preferences.addons.keys():
        helpers.render_resources_helper.init_gpu_states()

    # other stuff
    from . import ui
    from . import nodes
    from . import editor_nodes
    from . import editor_sockets
    from . import material_browser
    from . import node_thumbnail
    from . import images

    import rprblender.converter

    rpraddon.register_all()

    ui.register()
    render.register()
    nodes.register()
    node_thumbnail.register()
    material_browser.register()
    images.register()

    # emulate 'load post' for non installed plugin
    logging.info('Try: Emulate load_post...', tag='addon')
    if __package__ not in bpy.context.user_preferences.addons.keys():
        logging.info('Emulate load_post...', tag='addon')
        load_post(bpy.context)
    logging.info('rpr.register - done')


def unregister():
    logging.debug('rpr.unregister')
    from . import ui
    from . import render
    from rprblender.render import engine
    from . import nodes
    from . import editor_nodes
    from . import editor_sockets
    from . import material_browser
    from . import node_thumbnail
    from . import helpers
    from . import properties
    from . import images

    images.unregister()
    material_browser.unregister()
    node_thumbnail.unregister()
    nodes.unregister()
    render.unregister()
    ui.unregister()

    rpraddon.unregister_all()
    helpers.unregister()
    properties.unregister()

    bpy.app.handlers.load_post.remove(load_post)
