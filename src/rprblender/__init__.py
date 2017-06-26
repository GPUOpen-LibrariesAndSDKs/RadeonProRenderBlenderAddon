#!python3

bl_info = {
    "name": "Radeon ProRender",
    "description": "Radeon ProRender rendering plugin for Blender.",
    "author": "AMD",
    "version": (1, 2, 0),
    "blender": (2, 78, 0),
    "location": "Info header, render engine menu",
    "warning": "",  # used for warning icon and text in addons panel
    "wiki_url": "https://radeon-prorender.github.io",
    "tracker_url": "https://firerender.freshdesk.com/support/discussions",
    "category": "Render"
}

import bpy

from . import logging
logging.debug("loading addon");

from . import config
from . import addon


class Addon(addon.Addon):
    pass


rpraddon = Addon()


def check_data_from_library():
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
def load_post(context):
    logging.info("load_post...")

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

    bpy.ops.wm.rpr_thumbnail_update_caller_operator()

    bpy.context.scene.rpr.render.environment.switch_sun_helper()

    check_data_from_library()

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
    from . import ui

    # switch space.tree_type when we changed render engine
    if prev_engine != scene.render.engine and scene.render.engine == 'RPR':
        if not ui.activate_editor(prev_nodeeditor_name):
            ui.activate_shader_editor()

    prev_engine = scene.render.engine
    prev_nodeeditor_name = ui.get_activate_editor_name()


bpy.app.handlers.scene_update_post.append(on_scene_update_post)


# this can be had on scene load, not persistent
@bpy.app.handlers.persistent
def frame_change_pre(scene):
    logging.debug("frame_change_pre", scene.frame_current)


bpy.app.handlers.frame_change_pre.append(frame_change_pre)


def register():
    logging.info('rpr.register')

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
