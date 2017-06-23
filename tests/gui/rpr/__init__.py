bl_info = {
    "name": "Radeon ProRender",
    "description": "Radeon ProRender rendering plugin for Blender.",
    "author": "AMD",
    "version": (0, 1),
    "blender": (2, 77, 0),
    "location": "Info header, render engine menu",
    "warning": "", # used for warning icon and text in addons panel
    "wiki_url": "https://radeon-prorender.github.io",
    "tracker_url": "https://firerender.freshdesk.com/support/discussions",
    "category": "Render"
    }

import bpy
import bgl

import numpy as np
import time
from pathlib import Path
import importlib 

class RenderOperator(bpy.types.Operator):
    bl_idname = "rpr.render"
    bl_label = "RPR Render Scene"
    bl_options = {'REGISTER', 'BLOCKING', 'PRESET' }

    def execute(self, context):
        print(context)
        
        return {'FINISHED'}


class TestOperator(bpy.types.Operator):
    bl_idname = "rpr.test"
    bl_label = "RPR Test"
    bl_options = {'REGISTER', 'BLOCKING', 'PRESET' }

    def execute(self, context):
        import extract_scene
        importlib.reload(extract_scene)

        for obj in list(extract_scene.parse_scene(bpy.context.scene)):
            print(obj['type'])
        
        return {'FINISHED'}


#https://www.blender.org/api/blender_python_api_2_77_3/bpy.types.RenderEngine.html#simple-render-engine
class RPRRender(bpy.types.RenderEngine):
    bl_idname = 'RPRRender'
    bl_label = 'Radeon ProRender'
    bl_use_preview = True

    def update(self, data=None, scene=None):#Export scene data for render
        print('update')

    def bake(self, scene, object, pass_type, pass_filter, object_id, pixel_array, num_pixels, depth, result):#Bake passes
        print('bake')

    def xxx(self):pass

    def render(self, scene):
        im = self.render_scene(scene, (640, 480))

        width = im.shape[1] 
        height = im.shape[0]
        
        pixel_count = width * height

        result = self.begin_result(0, 0, width, height)
        layer = result.layers[0].passes["Combined"]
        print(type(layer))
        layer.rect = im.reshape(-1, 4)
        print('end_result')
        self.end_result(result)

    def render_scene(self, scene, fb_size):
        import simple_render
        import extract_scene
        importlib.reload(simple_render)
        importlib.reload(extract_scene)

        #print("RPRRender.render_scene:", "preview" if self.is_preview else "no preview")

        scale = scene.render.resolution_percentage / 100.0
        width = int(scene.render.resolution_x * scale)
        height = int(scene.render.resolution_y * scale)

        extracted = extract_scene.parse_scene(scene)

        im = simple_render.render_to_buffer(
            extracted, 
            fb_size,
            Path(__file__).parent/'rpr_cache')

        return np.flipud(im) 


    view_updated = False
    def view_update(self, context):#Update on data changes for viewport render
        self.view_updated = True
        #here need to find out what actually changed. e.g. an object, camera, resolutions etc.

    view_draw_last_timestamp = 0
    im = None
    def view_draw(self, context):#Draw viewport render
        #print("view_draw")

        view_draw_timestamp = time.clock()
        view_draw_time_interval = view_draw_timestamp-self.view_draw_last_timestamp

        render_interval_seconds_min = 0.2
        if ((self.im is None) or (render_interval_seconds_min<view_draw_time_interval)) and self.view_updated:
            im = self.render_scene(context.scene, (context.region.width, context.region.height))

            #apply "linear tonemapping" and flip rows 
            rgb = im[:,:,0:3]
            a = im[:,:,3] 
            self.im = np.append(rgb/np.max(rgb), a.reshape(a.shape[0], a.shape[1], 1), 2)
        
            self.view_draw_last_timestamp = view_draw_timestamp 

            self.view_updated = False

        im = self.im
        width = im.shape[1] 
        height = im.shape[0]

        #buf = np.flipud(im).flatten().reshape(im.shape)
        buf = im 
        f = Path(__file__).parent/'test_view_draw.png'
        if not f.is_file():
            import struct
            assert buf.dtype == np.float32
            np.save(str(f), buf)

        glBuffer = bgl.Buffer(bgl.GL_FLOAT, [height, width, 4], buf)
        bgl.glRasterPos2i(0, 0)
        bgl.glDrawPixels(width, height, bgl.GL_RGBA, bgl.GL_FLOAT, glBuffer)

        self.tag_redraw()

    def update_script_node(self, node=None):#Compile shader script node
        print("update_script_node")

def add_pause_button(self, context):

    if 'RPRRender' == context.scene.render.engine:
        if 'RENDERED' == context.space_data.viewport_shade:
            #self.layout.prop(context.scene.rpr, "pause", icon="Pause", text="")
            print("add_pause_button to RENDERED view")
            pass

def register():
    bpy.utils.register_class(RenderOperator)
    bpy.utils.register_class(TestOperator)
    bpy.utils.register_class(RPRRender)

    bpy.types.VIEW3D_HT_header.append(add_pause_button)

    import  bl_ui 
    bl_ui.properties_render.RENDER_PT_render.COMPAT_ENGINES.add(RPRRender.bl_idname)
    bl_ui.properties_render.RENDER_PT_dimensions.COMPAT_ENGINES.add(RPRRender.bl_idname)
    
    

def unregister():

    import  bl_ui 
    bl_ui.properties_render.RENDER_PT_dimensions.COMPAT_ENGINES.remove(RPRRender.bl_idname)
    bl_ui.properties_render.RENDER_PT_render.COMPAT_ENGINES.remove(RPRRender.bl_idname)

    bpy.types.VIEW3D_HT_header.remove(add_pause_button)

    bpy.utils.unregister_class(RPRRender)
    bpy.utils.unregister_class(TestOperator)
    bpy.utils.unregister_class(RenderOperator)              

if __name__=='__main__':
    register()