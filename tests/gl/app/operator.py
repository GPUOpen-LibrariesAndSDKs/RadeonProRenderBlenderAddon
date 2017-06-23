import bpy
from bgl import *

import time
import ctypes
from pathlib import Path

class OffScreenDraw(bpy.types.Operator):
    bl_idname = "view3d.test_gl"
    bl_label = "View3D Test GL"

    _handle_draw = None
    is_enabled = False

    # manage draw handler
    @staticmethod
    def draw_callback_px(self, context):
        scene = context.scene
        aspect_ratio = scene.render.resolution_x / scene.render.resolution_y
        #print('draw_callback_px!', time.clock())
        self.thelib.libfun()
        self.thelib.libdraw()

    @staticmethod
    def handle_add(self, context):
        OffScreenDraw._handle_draw = bpy.types.SpaceView3D.draw_handler_add(
                self.draw_callback_px, (self, context),
                'WINDOW', 'POST_PIXEL',
                )

    @staticmethod
    def handle_remove():
        if OffScreenDraw._handle_draw is not None:
            bpy.types.SpaceView3D.draw_handler_remove(OffScreenDraw._handle_draw, 'WINDOW')

        OffScreenDraw._handle_draw = None

    # operator functions
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D'

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        print('invoke!', time.clock())

        if OffScreenDraw.is_enabled:
            self.cancel(context)
            del OffScreenDraw.thelib

            return {'FINISHED'}

        OffScreenDraw.thelib = ctypes.cdll.LoadLibrary(str(Path(__file__).parent/'.build/Debug/lib.dll'))

        OffScreenDraw.is_enabled = True

        OffScreenDraw.handle_add(self, context)

        if context.area:
            context.area.tag_redraw()

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        print('cancel!', time.clock())
        OffScreenDraw.handle_remove()
        OffScreenDraw.is_enabled = False

        if context.area:
            context.area.tag_redraw()


def register():
    bpy.utils.register_class(OffScreenDraw)


def unregister():
    bpy.utils.unregister_class(OffScreenDraw)


if __name__ == "__main__":
    register()
