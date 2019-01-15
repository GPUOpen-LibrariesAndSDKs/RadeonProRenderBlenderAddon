import bpy

bl_info = {
    "name": "Radeon ProRender",
    "author": "AMD",
    "version": (2, 0, 1),
    "blender": (2, 80, 0),
    "location": "Info header, render engine menu",
    "description": "Radeon ProRender rendering plugin for Blender 2.8x",
    "warning": "",
    "tracker_url": "",
    "wiki_url": "",
    "category": "Render"
}



from .utils import logging

plugin_log = logging.Log(tag="Plugin")
plugin_log("Loading RPR addon {}".format(bl_info['version']))
log = logging.Log(tag='RPREngine')


from .engine.engine import Engine
from . import (
    nodes,
    properties,
    ui,
    operators,
)

from .engine.render_engine import RenderEngine
from .engine.preview_engine import PreviewEngine
from .engine.viewport_engine import ViewportEngine


class RPREngine(bpy.types.RenderEngine):
    ''' These members are used by blender to set up the
        RenderEngine; define its internal name, visible name and capabilities. '''
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
        ''' Called for final render '''
        log('update')

        if not self.engine:
            if self.is_preview:
                self.engine = PreviewEngine(self)
            else:
                self.engine = RenderEngine(self)

        self.engine.sync(depsgraph)

    def render(self, depsgraph):
        ''' Called with both final render and viewport '''
        log("render")

        self.engine.render()

    # viewport render
    def view_update(self, context):
        ''' called when data is updated for viewport '''
        log('view_update')

        # if there is no engine set, create it and do the initial sync
        if not self.engine:
            self.engine = ViewportEngine(self)  # ,context.region, context.space_data, context.region_data)
            self.engine.sync(context.depsgraph)
            self.engine.render()
        else:
            self.engine.sync_updated(context.depsgraph)

    def view_draw(self, context):
        ''' called when viewport is to be drawn '''
        self.engine.draw(context)


@bpy.app.handlers.persistent
def on_load_post(dummy):
    plugin_log("on_load_post...")

    properties.material.activate_shader_editor()

    plugin_log("load_post ok")


def register():
    bpy.utils.register_class(RPREngine)
    properties.register()
    operators.register()
    nodes.register()
    ui.set_rpr_panels_filter()
    ui.register()
    bpy.app.handlers.load_post.append(on_load_post)


def unregister():
    bpy.app.handlers.load_post.remove(on_load_post)
    ui.remove_rpr_panels_filter()
    ui.unregister()
    nodes.unregister()
    operators.unregister()
    properties.unregister()
    bpy.utils.unregister_class(RPREngine)

