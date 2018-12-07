import bpy
from .engine.engine import Engine
from . import properties
from . import logging


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

logging.info("Loading RPR addon {}".format(bl_info['version']))


class RPREngine(bpy.types.RenderEngine):
    ''' These members are used by blender to set up the
        RenderEngine; define its internal name, visible name and capabilities. '''
    bl_idname = "RPR"
    bl_label = "Radeon ProRender"
    bl_use_preview = True
    bl_use_shading_nodes = True
    bl_info = "Radeon ProRender rendering plugin"

    def __init__(self):
        self.engine: Engine = None

    # final render
    def update(self, data, depsgraph):
        ''' Called for final render '''
        logging.info('render_engine.update')

        if not self.engine:
            self.engine = Engine(self)

        self.engine.sync(depsgraph)

    def render(self, depsgraph):
        ''' Called with both final render and viewport '''
        logging.info("render_engine.render")

        self.engine.render(depsgraph)
        image = self.engine.get_image()

        result = self.begin_result(0, 0, image.shape[1], image.shape[0])
        image = image.reshape((image.shape[1]*image.shape[0], 4))
        layer = result.layers[0].passes["Combined"]
        layer.rect = image
        self.end_result(result)



    # viewport render
    def view_update(self, context):
        ''' called when data is updated for viewport '''
        logging.info('render_engine.view_update')

        # if there is no engine set, create it and do the initial sync
        if not self.engine:
            self.engine = Engine(self)  # ,context.region, context.space_data, context.region_data)
            self.engine.sync(context.depsgraph)
        else:
            self.engine.sync_updated(context.depsgraph)

    def view_draw(self, context):
        ''' called when viewport is to be drawn '''
        logging.info('render_engine.view_draw')

        self.engine.draw(context.depsgraph, context.region, context.space_data, context.region_data)


def register():
    bpy.utils.register_class(RPREngine)
    properties.register()


def unregister():
    properties.unregister()
    bpy.utils.unregister_class(RPREngine)
