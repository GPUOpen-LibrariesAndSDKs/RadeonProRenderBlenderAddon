import traceback

import bpy


bl_info = {
    "name": "Radeon ProRender",
    "author": "AMD",
    "version": (2, 2, 3),
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
from .engine.animation_engine import AnimationEngine

from .engine.render_engine_hybrid import RenderEngine as RenderEngineHybrid
from .engine.viewport_engine_hybrid import ViewportEngine as ViewportEngineHybrid
from .engine.animation_engine_hybrid import AnimationEngine as AnimationEngineHybrid

log = logging.Log(tag='init')
log("Loading RPR addon {}".format(bl_info['version']))


def ensure_boto3() -> None:
    """
    WIP "try to install boto3 library at the addon launch time" for zip archive distribution type
    """
    # TODO: test on MacOS
    # TODO: test on Ubuntu
    # TODO: test if no Python present at all on Windows
    # use this snippet to install boto3 library with all the dependencies if absent at the addon launch time
    # note: still it will be available at the next Blender launch only
    # TODO: check if scene reload works as well (note: even then it couldn't be used at all; just to be sure on how it works)
    try:
        import boto3
        log.info("boto3 is already available")
    except ImportError:
        log.info("Installing boto3 library...")
        import subprocess
        # subprocess.call([bpy.app.binary_path_python, "-m", "ensurepip"])  # seems to be working fine without it
        subprocess.call([bpy.app.binary_path_python, "-m", "pip", "install", "--upgrade", "pip", "--user"])
        subprocess.call([bpy.app.binary_path_python, "-m", "pip", "install", "boto3", "--user"])
        log.info("Library boto3 should be available after Blender restart")


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
        log('__del__', self.as_pointer())

        if isinstance(self.engine, ViewportEngine):
            self.engine.stop_render()

    # final render
    def update(self, data, depsgraph):
        """ Called for final render """
        log('update', self.as_pointer())

        # TODO: We create for every view layer separate Engine. We should improve this by implementing sync_update()
        try:
            is_hybrid = depsgraph.scene.rpr.is_hybrid
            if self.is_preview:
                self.engine = PreviewEngine(self)

            elif self.is_animation:
                if is_hybrid:
                    self.engine = AnimationEngineHybrid(self)
                else:
                    self.engine = AnimationEngine(self)

            else:
                if is_hybrid:
                    self.engine = RenderEngineHybrid(self)
                else:
                    self.engine = RenderEngine(self)

            self.engine.sync(depsgraph)

        except Exception as e:
            log.error(e, 'EXCEPTION:', traceback.format_exc())
            self.error_set(f"ERROR | {e}. Please see log for more details.")

    def render(self, depsgraph):
        """ Called with both final render and viewport """
        log("render", self.as_pointer())
        try:
            self.engine.render()

        except Exception as e:
            log.error(e, 'EXCEPTION:', traceback.format_exc())
            self.error_set(f"ERROR | {e}. Please see log for more details.")

    # viewport render
    def view_update(self, context, depsgraph):
        """ called when data is updated for viewport """
        log('view_update', self.as_pointer())

        try:
            # if there is no engine set, create it and do the initial sync
            is_hybrid = depsgraph.scene.rpr.is_hybrid
            if self.engine and is_hybrid ^ isinstance(self.engine, ViewportEngineHybrid) == 0:
                self.engine.sync_update(context, depsgraph)
                return

            if self.engine:
                self.engine.stop_render()

            if is_hybrid:
                self.engine = ViewportEngineHybrid(self)
            else:
                self.engine = ViewportEngine(self)
            self.engine.sync(context, depsgraph)

        except Exception as e:
            log.error(e, 'EXCEPTION:', traceback.format_exc())

    def view_draw(self, context, depsgraph):
        """ called when viewport is to be drawn """
        log('view_draw', self.as_pointer())

        try:
            self.engine.draw(context)

        except Exception as e:
            log.error(e, 'EXCEPTION:', traceback.format_exc())

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
    """ Register all addon classes in Blender """
    log("register")
    ensure_boto3()

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
    """ Unregister all addon classes from Blender """
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
