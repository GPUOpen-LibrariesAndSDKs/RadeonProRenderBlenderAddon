import numpy as np

from . import RPR_Properties
import bpy

import pyrpr
from rprblender import logging


def log(*args):
    logging.info(*args, tag='Mesh')


class RPR_MeshProperties(RPR_Properties):
    ''' Properties for mesh '''

    def sync(self, context, transform):
        ''' sync the mesh '''
        mesh = self.id_data
        log("Syncing mesh: %s" % mesh.name)

        # preparing mesh to export
        mesh.calc_normals_split()
        mesh.calc_loop_triangles()
        
        # getting mesh export data
        tris_len = len(mesh.loop_triangles)
        if tris_len == 0:
            return

        vertices = np.array([vert.co for vert in mesh.vertices], dtype=np.float32)
        normals = np.array([norm for tri in mesh.loop_triangles
                              for norm in tri.split_normals], dtype=np.float32)
        uvs = None  # np.full((tris_len*3, 2), [0., 0.], dtype=np.float32)

        num_face_vertices = np.full((tris_len,), 3)
        vertex_indices = np.array([tri.vertices for tri in mesh.loop_triangles]).reshape((tris_len*3,))
        normal_indices = np.arange(tris_len*3)
        uv_indices = None   # normal_indices

        # creating RPR mesh
        rpr_mesh = context.create_mesh(vertices, normals, uvs,
                                vertex_indices, normal_indices, uv_indices,
                                num_face_vertices)

        rpr_mesh.set_name(mesh.name)
        rpr_mesh.set_transform(transform)

    @classmethod
    def register(cls):
        log("Register")
        bpy.types.Mesh.rpr = bpy.props.PointerProperty(
            name="RPR Mesh Settings",
            description="RPR object settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Unregister")
        del bpy.types.Mesh.rpr


classes_to_register = (RPR_MeshProperties,)
