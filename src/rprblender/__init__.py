import bpy


bl_info = {
    "name": "Radeon ProRender",
    "author": "AMD",
    "version": (2, 0, 125),
    "blender": (2, 80, 0),
    "location": "Info header, render engine menu",
    "description": "Radeon ProRender rendering plugin for Blender 2.8x",
    "warning": "",
    "tracker_url": "",
    "wiki_url": "",
    "category": "Render"
}

from .utils import logging, version_updater

from .engine.engine import Engine
from . import (
    nodes,
    properties,
    ui,
    operators,
    material_library,
)

from .engine.render_engine import RenderEngine
from .engine.preview_engine import PreviewEngine
from .engine.viewport_engine import ViewportEngine


log = logging.Log(tag='init')
log("Loading RPR addon {}".format(bl_info['version']))


class RPREngine(bpy.types.RenderEngine):
    """
    Main class of Radeon ProRender render engine for Blender v2.80+
    """
    bl_idname = "RPR"
    bl_label = "Radeon ProRender"
    bl_use_preview = True
    bl_use_shading_nodes = True
    bl_use_shading_nodes_custom = False
    bl_info = "Radeon ProRender rendering plugin"

    engine: Engine = None

    def __del__(self):
        if isinstance(self.engine, ViewportEngine):
            self.engine.stop_render()

    # final render
    def update(self, data, depsgraph):
        """ Called for final render """
        log('update')

        # TODO: We create for every view layer separate Engine. We should improve this by implementing sync_update()
        if self.is_preview:
            self.engine = PreviewEngine(self)
        else:
            self.engine = RenderEngine(self)

        self.engine.sync(depsgraph)

    def render(self, depsgraph):
        """ Called with both final render and viewport """
        log("render")

        self.engine.render()

    # viewport render
    def view_update(self, context, depsgraph):
        """ called when data is updated for viewport """
        log('view_update')

        # if there is no engine set, create it and do the initial sync
        if not self.engine:
            self.engine = ViewportEngine(self)
            self.engine.sync(context, depsgraph)
            self.engine.render()
        else:
            self.engine.sync_update(context, depsgraph)

    def view_draw(self, context, depsgraph):
        """ called when viewport is to be drawn """
        self.engine.draw(context)

    # view layer AOVs
    def update_render_passes(self, render_scene=None, render_layer=None):
        """
        Update 'Render Layers' compositor node with active render passes info.
        Called by Blender.
        """
        aovs = properties.view_layer.RPR_ViewLayerProperites.aovs_info

        scene = render_scene if render_scene else bpy.context.scene
        layer = render_layer if render_scene else bpy.context.view_layer

        for index, enabled in enumerate(layer.rpr.enable_aovs):
            if enabled:
                pass_channel = aovs[index]['channel']
                pass_name = aovs[index]['name']
                pass_channels_size = len(pass_channel)

                # convert from channel to blender type
                blender_type = 'VALUE'
                if pass_channel in ('RGB', 'RGBA'):
                    blender_type = 'COLOR'
                elif pass_channel in {'XYZ', 'UVA'}:
                    blender_type = 'VECTOR'

                self.register_pass(scene, layer,
                                   pass_name, pass_channels_size, pass_channel, blender_type)

@bpy.app.handlers.persistent
def on_version_update(*args, **kwargs):
    """ On scene loading update old RPR data to current version """
    log("on_version_update")

    addon_version = bl_info['version']
    if version_updater.is_scene_saved_by_older_addon_version(addon_version):
        version_updater.update_old_scene()


@bpy.app.handlers.persistent
def on_save_pre(*args, **kwargs):
    """ Handler on saving a blend file (before) """
    log("on_save_pre")

    # Save current plugin version in scene
    bpy.context.scene.rpr.saved_addon_version = bl_info['version']


@bpy.app.handlers.persistent
def on_load_pre(*args, **kwargs):
    """ Handler on loading a blend file (before) """
    log("on_load_pre")

    utils.clear_temp_dir()


def register():
    log("register")

    bpy.utils.register_class(RPREngine)
    material_library.register()
    properties.register()
    operators.register()
    nodes.register()
    ui.register()

    bpy.app.handlers.save_pre.append(on_save_pre)
    bpy.app.handlers.load_pre.append(on_load_pre)
    bpy.app.handlers.version_update.append(on_version_update)


def unregister():
    log("unregister")

    bpy.app.handlers.version_update.remove(on_version_update)
    bpy.app.handlers.load_pre.remove(on_load_pre)
    bpy.app.handlers.save_pre.remove(on_save_pre)

    ui.unregister()
    nodes.unregister()
    operators.unregister()
    properties.unregister()
    material_library.unregister()
    bpy.utils.unregister_class(RPREngine)
