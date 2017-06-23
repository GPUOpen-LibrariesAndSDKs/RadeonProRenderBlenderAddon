import bpy

import sys


import time

def log_updates(name, scene, force_output=True):
    logged = False
    for obj in bpy.data.objects:
        some_updated = obj.is_updated or obj.is_updated_data or (obj.data.is_updated if obj.data else None) 
        
        if some_updated:
            if not logged:
                print(name+':', time.time())
                logged = True

            print("    ", obj, obj.is_updated, obj.is_updated_data, obj.data.is_updated if obj.data else None)
    if not logged and force_output:
        print(name+':', time.time())
        print('    <nothing>')
        
    sys.stdout.flush()

def update_pre(scene):
    log_updates('update_pre', scene, force_output=False) 

def update_post(scene):
    log_updates('update_post', scene, force_output=False) 

bpy.app.handlers.scene_update_pre.append(update_pre)
bpy.app.handlers.scene_update_post.append(update_post)

scene = bpy.context.scene

cube = bpy.context.object

bpy.context.object.location = (0, 1, 0)

log_updates("bpy.context.object.location", scene)

bpy.ops.group.create()
log_updates("bpy.ops.group.create()", scene)

group = bpy.ops.object.group_instance_add(
    group='Group',
    location=(2, 0, 0))
log_updates("bpy.ops.object.group_instance_add", scene)
bpy.context.object.name = 'CubeTwin'
log_updates("bpy.context.object.name", scene)

for window in bpy.context.window_manager.windows:
    screen = window.screen

    for area in screen.areas:
        if area.type == 'VIEW_3D':
            for region in area.regions:
                if region.type == 'WINDOW':
                    override = {
                        'window': window, 
                        'screen': screen, 
                        'area': area, 
                        'region':region,
                        'edit_object':cube
                        }
                    log_updates("edit before started", scene)
                    bpy.context.scene.objects.active = cube
                    log_updates("activated", scene)
                    bpy.ops.object.mode_set(mode='EDIT')
                    log_updates("mode  - edit ", scene)
                    bpy.ops.mesh.subdivide(smoothness=1)
                    log_updates("subdivided", scene)
                    bpy.ops.object.mode_set(mode='OBJECT')
                    log_updates("mode  - object", scene)
                    break
                    
scene.update()#make sure everythin is updated in accordance to made changes

for obj in scene.objects:
    if obj.dupli_type=='GROUP': 
        obj.dupli_list_create(scene, settings='RENDER')

        for dupli in obj.dupli_list:
            print(dupli.matrix)

        obj.dupli_list_clear()

print('done');sys.stdout.flush()
