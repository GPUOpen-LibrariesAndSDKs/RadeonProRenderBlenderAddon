import bpy

scene = bpy.context.scene

for object in scene.objects:
    print(object)
    object_type = object.type

    print(repr(object_type))
    if 'MESH' == object_type: 
        mesh = object.data
        print('   ', 'mesh:', mesh, type(mesh))
        vertices = mesh.vertices
        print('    '*2, 'vertices:', len(vertices))
        print('    '*2, 'methods:')
        for m in dir(mesh):
            pass#print('    '*3, m)

        v = vertices[0]
        print(v, dir(v))

        polygons = mesh.polygons

        print('    '*2, 'polygons:', len(polygons))

        p = polygons[0]
        print(p, dir(p))
        print(list(p.vertices))

        loops = mesh.loops
        print('    '*2, 'loops:', len(loops))


    #for m in dir(object):
    #    print(m, end=', ')



#bpy.context.window_manager.fileselect_add(operator)
