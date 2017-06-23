#!python3

bl_info = {
    "name": "Test",
    "description": "Test sleep(0) in RenderEngine vieport thread",
    "author": "",
    "version": (0, 0, 1),
    "blender": (2, 78, 0),
    "location": "Info header, render engine menu",
    "warning": "", # used for warning icon and text in addons panel
    "category": "Render"
    }


import bpy

import time
import threading

class MyThread(threading.Thread):

    def run(self):
        while True:
            time.sleep(0)

class ThreadStartOperator(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "test.thread_start"
    bl_label = "Test Start Thread"

    def execute(self, context):
        global thread 
        thread = MyThread()
        thread.start()
        return {'FINISHED'}

class TestEngine(bpy.types.RenderEngine):
    bl_idname = 'TEST'
    bl_label = 'Test'

    def __init__(self):
        super().__init__()
        pass

    def view_update(self, context):#Update on data changes for viewport render
        pass

    def view_draw(self, context): # Draw viewport render
        pass

def register():
    bpy.utils.register_class(TestEngine)
    bpy.utils.register_class(ThreadStartOperator)

