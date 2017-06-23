import numpy as np

def parse_scene(scene):
    
    for object in scene.objects:
        #print(object)
        object_type = object.type
    
        #print(repr(object_type))


        if 'CAMERA' == object_type:
            camera = object.data
            
            yield dict(
                type=object_type,
                matrix_world=np.array(object.matrix_world, dtype=np.float32),
                data={
                    'type':camera.type,#‘PERSP’, ‘ORTHO’, ‘PANO’
                    'lens': camera.lens,
                    'dof_distance':camera.dof_distance,
                    'sensor_width':camera.sensor_width,
                    'sensor_height':camera.sensor_height,
                    'fstop':camera.gpu_dof.fstop,
                    }
                )

        elif 'MESH' == object_type:
            mesh = object.data

            #print('   ', 'mesh:', mesh)
    
            vertices = np.empty(len(mesh.vertices)*3, dtype=np.float32) 
            mesh.vertices.foreach_get('co', vertices)
    
            normals = np.empty(len(mesh.vertices)*3, dtype=np.float32) 
            mesh.vertices.foreach_get('normal', normals)
    
            faces_list = [np.array(p.vertices, dtype=np.int32) for p in mesh.polygons]
    
            faces_counts = np.array([len(l) for l in faces_list], dtype=np.int32)

            indices = np.concatenate(faces_list)

            #print("indices:", indices)
            #print("indices.shape:", indices.shape)

            yield dict(
                type=object_type,
                matrix_world=np.array(object.matrix_world, dtype=np.float32),
                data=dict(                
                    vertices=vertices.reshape(-1, 3), 
                    normals=normals.reshape(-1, 3), 
                    indices=indices, 
                    faces_counts=faces_counts,
                    )
                )
        else:
            yield dict(
                type=object_type,
                matrix_world=np.array(object.matrix_world, dtype=np.float32),
                )

if __name__=='__main__':
    import bpy
    print('>>>')
    for o in parse_scene(bpy.context.scene):
        print(o)          
    print('<<<')           

