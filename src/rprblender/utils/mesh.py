import numpy as np

import bpy
from rprblender.properties import SyncError


def get_mesh_properties(mesh:bpy.types.Mesh, calc_area=False):
    # preparing mesh to export
    mesh.calc_normals_split()
    mesh.calc_loop_triangles()

    # getting mesh export data
    tris_len = len(mesh.loop_triangles)
    if tris_len == 0:
        raise SyncError("Mesh %s has no polygons" % mesh.name, mesh)

    vertices = np.array([vert.co for vert in mesh.vertices], dtype=np.float32)
    normals = np.array(
        [norm for tri in mesh.loop_triangles
              for norm in tri.split_normals],
        dtype=np.float32
    )

    uvs = None
    uv_indices = None
    if len(mesh.uv_layers) > 0:
        uv_layer = mesh.uv_layers.active
        uvs = np.array([[d.uv.x, d.uv.y] for d in uv_layer.data], dtype=np.float32)
        uv_indices = np.array([tri.loops for tri in mesh.loop_triangles], dtype=np.int32).reshape((tris_len * 3,))

    num_face_vertices = np.full((tris_len,), 3, dtype=np.int32)
    vertex_indices = np.array([tri.vertices for tri in mesh.loop_triangles], dtype=np.int32).reshape((tris_len * 3,))
    normal_indices = np.arange(tris_len * 3, dtype=np.int32)

    mesh_prop = {
        'vertices': vertices,
        'normals': normals,
        'uvs': uvs,
        'vertex_indices': vertex_indices,
        'normal_indices': normal_indices,
        'uv_indices': uv_indices,
        'num_face_vertices': num_face_vertices,
    }

    if calc_area:
        mesh_prop['area'] = sum(tri.area for tri in mesh.loop_triangles)

    return mesh_prop

