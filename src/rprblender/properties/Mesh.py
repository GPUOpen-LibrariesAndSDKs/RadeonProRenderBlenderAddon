from .base import RPR_Property
from bpy.props import *
import bpy

import pyrpr

class MeshProperties(RPR_Property):
    ''' Properties for mesh '''

    def sync(self, context):
        ''' sync the mesh '''
        mesh = self.id_data
        print("Syncing Mesh %s " % mesh.name)

    @classmethod
    def register(cls):
        bpy.types.Mesh.rpr = PointerProperty(
            name="RPR Mesh Settings",
            description="RPR object settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        del bpy.types.Mesh.rpr


classes = (MeshProperties,)
