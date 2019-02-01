from dataclasses import dataclass
import numpy as np

import bpy
from rprblender.properties import SyncError


@dataclass(init=False)
class MeshData:
    vertices: np.array
    normals: np.array
    uvs: np.array
    vertex_indices: np.array
    normal_indices: np.array
    uv_indices: np.array
    num_face_vertices: np.array
    area: float = None


def get_mesh_data(mesh:bpy.types.Mesh, calc_area=False):
    data = MeshData()

    # preparing mesh to export
    mesh.calc_normals_split()
    mesh.calc_loop_triangles()

    # getting mesh export data
    tris_len = len(mesh.loop_triangles)
    if tris_len == 0:
        raise SyncError("Mesh %s has no polygons" % mesh.name, mesh)

    data.vertices = np.array([vert.co for vert in mesh.vertices], dtype=np.float32)
    data.normals = np.array(
        [norm for tri in mesh.loop_triangles
              for norm in tri.split_normals],
        dtype=np.float32
    )

    data.uvs = None
    data.uv_indices = None
    if len(mesh.uv_layers) > 0:
        uv_layer = mesh.uv_layers.active
        uvs = np.array([[d.uv.x, d.uv.y] for d in uv_layer.data], dtype=np.float32)
        if len(uvs) > 0:
            data.uvs = uvs
            data.uv_indices = np.array([tri.loops for tri in mesh.loop_triangles], dtype=np.int32).reshape((tris_len * 3,))

    data.num_face_vertices = np.full((tris_len,), 3, dtype=np.int32)
    data.vertex_indices = np.array([tri.vertices for tri in mesh.loop_triangles], dtype=np.int32).reshape((tris_len * 3,))
    data.normal_indices = np.arange(tris_len * 3, dtype=np.int32)

    if calc_area:
        data.area = sum(tri.area for tri in mesh.loop_triangles)

    return data
