import numpy as np
import math

import bmesh
import mathutils


def convert_kelvins_to_rgb(colour_temperature: int) -> tuple:
    # range check
    if colour_temperature < 1000:
        colour_temperature = 1000
    elif colour_temperature > 40000:
        colour_temperature = 40000

    tmp_internal = colour_temperature / 100.0
    # red
    if tmp_internal <= 66:
        red = 255
    else:
        tmp_red = 329.698727446 * math.pow(tmp_internal - 60, -0.1332047592)
        red = max(0, min(tmp_red, 255))

    # green
    if tmp_internal <= 66:
        tmp_green = 99.4708025861 * math.log(tmp_internal) - 161.1195681661
        green = max(0, min(tmp_green, 255))
    else:
        tmp_green = 288.1221695283 * math.pow(tmp_internal - 60, -0.0755148492)
        green = max(0, min(tmp_green, 255))

    # blue
    if tmp_internal >= 66:
        blue = 255
    elif tmp_internal <= 19:
        blue = 0
    else:
        tmp_blue = 138.5177312231 * math.log(tmp_internal - 10) - 305.0447927307
        blue = max(0, min(tmp_blue, 255))

    return (red / 255.0, green / 255.0, blue / 255.0)


def get_area_light_mesh_properties(shape_type, size, size_y, segments):
    bm = bmesh.new()
    try:
        if shape_type in ('SQUARE', 'RECTANGLE'):
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)

        elif shape_type in ('DISK', 'ELLIPSE'):
            bmesh.ops.create_circle(bm, cap_ends=True, cap_tris=True, segments=segments, radius=0.5)

        else:
            raise TypeError("Incorrect shape type", shape_type)

        # getting uvs before modifying mesh
        bm.verts.ensure_lookup_table()
        uvs = np.array([(vert.co[0] + 0.5, vert.co[1] + 0.5) for vert in bm.verts], dtype=np.float32)

        # scale and rotate mesh around Y axis
        bmesh.ops.scale(bm, verts=bm.verts,
                        vec=(size, size if shape_type in ('SQUARE', 'DISK') else size_y, 1.0))
        bmesh.ops.rotate(bm, verts=bm.verts,
                         matrix=mathutils.Matrix.Rotation(math.pi, 4, 'Y'))

        # preparing mesh to get data
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        loop_triangles = bm.calc_loop_triangles()
        tris_len = len(loop_triangles)

        vertices = np.array([vert.co for vert in bm.verts], dtype=np.float32)
        normals = np.array([vert.normal for vert in bm.verts], dtype=np.float32)

        num_face_vertices = np.full((tris_len,), 3, dtype=np.int32)
        vertex_indices = np.array([vert.vert.index for tri in loop_triangles for vert in tri], dtype=np.int32)

        area = sum(face.calc_area() for face in bm.faces)

        return {
            'vertices': vertices,
            'normals': normals,
            'uvs': uvs,
            'vertex_indices': vertex_indices,
            'normal_indices': vertex_indices,
            'uv_indices': vertex_indices,
            'num_face_vertices': num_face_vertices,
            'area': area,
        }

    finally:
        bm.free()
