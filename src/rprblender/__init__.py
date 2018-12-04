import bpy
from .engine.engine import Engine
from . import properties, nodes


bl_info = {
    "name": "RPR Test Render Engine",
    "author": "",
    "blender": (2, 80, 0),
    "location": "Info header, render engine menu",
    "description": "RPR test Render Engine integration",
    "warning": "",
    "tracker_url": "",
    "category": "Render"}


class CustomRenderEngine(bpy.types.RenderEngine):
    ''' These members are used by blender to set up the
        RenderEngine; define its internal name, visible name and capabilities. '''
    bl_idname = "RPR"
    bl_label = "RPR Test Renderer"
    bl_use_preview = True
    bl_use_shading_nodes = True
    bl_info = "RPR Test Render"

    engine = None

    # final render
    def update(self, data, depsgraph):
        ''' Called for final render '''
        print('render_engine.update')

        if not self.engine:
            self.engine = Engine(self, data)

        self.engine.sync(data, depsgraph)

    def render(self, depsgraph):
        ''' Called with both final render and viewport '''
        print('render_engine.render')
        
        self.engine.render(depsgraph)


    # viewport render
    def view_update(self, context):
        ''' called when data is updated for viewport '''
        print('render_engine.view_update')
        
        # if there is no engine set, create it and do the initial sync
        if not self.engine:
            self.engine = Engine(self, context.blend_data) #,context.region, context.space_data, context.region_data)
            self.engine.sync(context.blend_data, context.depsgraph)
        # else just update updated stuff
        else:
            self.engine.sync_updated(context.blend_data, context.depsgraph)

    def view_draw(self, context):
        ''' called when viewport is to be drawn '''
        print('render_engine.view_draw')
        
        self.engine.draw(context.depsgraph) #, context.region, context.space_data, context.region_data)


def register():
    properties.register()
    nodes.register()
    # Register the RenderEngine
    bpy.utils.register_class(CustomRenderEngine)


def unregister():
    properties.unregister()
    nodes.unregister()
    bpy.utils.unregister_class(CustomRenderEngine)

