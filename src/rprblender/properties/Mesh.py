import numpy as np

from . import RPR_Properties
from bpy.props import *
import bpy

import pyrpr
from rprblender import logging

class RPR_MeshProperties(RPR_Properties):
    ''' Properties for mesh '''

    def sync(self, context, transform):
        ''' sync the mesh '''
        mesh = self.id_data
        print("Syncing mesh: %s" % mesh.name)

        vertices = np.array([
            [ 1.        ,  0.99999994, -1.        ],
            [ 1.        , -1.        , -1.        ],
            [-1.00000012, -0.99999982, -1.        ],
            [-0.99999964,  1.00000036, -1.        ],
            [ 1.00000048,  0.99999946,  1.        ],
            [ 0.99999934, -1.0000006 ,  1.        ],
            [-1.00000036, -0.99999964,  1.        ],
            [-0.99999994,  1.        ,  1.        ]], dtype=np.float32)

        normals = np.array([
            [ 0.,  0., -1.],
            [ 0.,  0., -1.],
            [ 0.,  0., -1.],
            [ 0.,  0., -1.],
            [ 0.,  0.,  1.],
            [ 0.,  0.,  1.],
            [ 0.,  0.,  1.],
            [ 0.,  0.,  1.],
            [ 1.,  0.,  0.],
            [ 1.,  0.,  0.],
            [ 1.,  0.,  0.],
            [ 1.,  0.,  0.],
            [ 0., -1.,  0.],
            [ 0., -1.,  0.],
            [ 0., -1.,  0.],
            [ 0., -1.,  0.],
            [-1.,  0.,  0.],
            [-1.,  0.,  0.],
            [-1.,  0.,  0.],
            [-1.,  0.,  0.],
            [ 0.,  1.,  0.],
            [ 0.,  1.,  0.],
            [ 0.,  1.,  0.],
            [ 0.,  1.,  0.]], dtype=np.float32)

        uvs = np.array([
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.],
            [ 0.,  0.]], dtype=np.float32)

        vertex_indices = np.array([0, 1, 2, 3, 4, 7, 6, 5, 0, 4, 5, 1, 1, 5, 6, 2, 2, 6, 7, 3, 4, 0, 3, 7])
        normal_indices = np.array([ 0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23])
        texcoord_indices = normal_indices
        num_face_vertices = np.array([4, 4, 4, 4, 4, 4])

        rpr_mesh = context.create_mesh(vertices, normals, uvs,
                                vertex_indices, normal_indices, texcoord_indices,
                                num_face_vertices)

        rpr_mesh.set_name(mesh.name)
        rpr_mesh.set_transform(transform)



    @classmethod
    def register(cls):
        logging.info("register", tag='Mesh')
        bpy.types.Mesh.rpr = PointerProperty(
            name="RPR Mesh Settings",
            description="RPR object settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        logging.info("unregister", tag='Mesh')
        del bpy.types.Mesh.rpr


classes_to_register = (RPR_MeshProperties,)
