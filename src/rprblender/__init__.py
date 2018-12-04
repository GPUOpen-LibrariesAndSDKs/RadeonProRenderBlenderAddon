import bpy
from .engine.engine import Engine


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


class RPREngine(bpy.types.RenderEngine):
    ''' These members are used by blender to set up the
        RenderEngine; define its internal name, visible name and capabilities. '''
    bl_idname = "RPR"
    bl_label = "Radeon ProRender"
    bl_use_preview = True
    bl_use_shading_nodes = True
    bl_info = "Radeon ProRender rendering plugin"

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


register, unregister = bpy.utils.register_classes_factory({RPREngine})
