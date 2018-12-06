from .base import RPR_Property
from bpy.props import *
import bpy

import pyrpr
from rprblender import logging

class MeshProperties(RPR_Property):
    ''' Properties for mesh '''

    def sync(self, context):
        ''' sync the mesh '''
        mesh = self.id_data
        print("Syncing mesh: %s" % mesh.name)

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


classes = (MeshProperties,)
