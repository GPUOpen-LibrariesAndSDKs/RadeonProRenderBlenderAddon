import bpy
import os
import traceback
import time
import sys


import rprblender.material_browser

def test():
    context = bpy.context

    override = {}
    override.update({
     "material": context.object.active_material
     , "screen": context.screen
     , "scene": context.scene
     , "active_object": context.object
     , "blend_data": bpy.data
     , "region": context.region
     , "node": [] # i dont know what this should point at
     , "window": context.window
    })

    mlp = context.window_manager.rpr_material_library_properties
    mlp.categories
    mlp.materials
    
    #  bpy.ops.rpr.import_material_operator(override)
    try:
        bpy.ops.rpr.import_materials_test_operator(override)
    except:
        print(traceback.format_exc())
    sys.stdout.flush()
    

class ModalTimerOperator(bpy.types.Operator):
    """Operator which runs its self from a timer"""
    bl_idname = "rpr.test_import_stress"
    bl_label = "Modal Timer Operator"

    _timer = None

    def modal(self, context, event):
        print('modal!!!!!!!!!')
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            if rprblender.material_browser.RPRImportMaterialsTestOperator.done_all:
                rprblender.material_browser.RPRImportMaterialsTestOperator.last_index = 0
                rprblender.material_browser.RPRImportMaterialsTestOperator.done_all = False
                # self.cancel(context)
                # return {'CANCELLED'}
    
            print('test!!!!!!!!!')
            test()

        return {'PASS_THROUGH'}

    def execute(self, context):
        print('execute!!!!!!!!!')

        rprblender.material_browser.RPRImportMaterialsTestOperator.last_index = 0
        rprblender.material_browser.RPRImportMaterialsTestOperator.done_all = False

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        print('cancel!!!!!!!!!')
        wm = context.window_manager
        wm.event_timer_remove(self._timer)


def register():
    bpy.utils.register_class(ModalTimerOperator)


def unregister():
    bpy.utils.unregister_class(ModalTimerOperator)


if __name__ == "__main__":
    register()
    print('hello!!!!!!!!!')
    # test call
    bpy.ops.rpr.test_import_stress()
