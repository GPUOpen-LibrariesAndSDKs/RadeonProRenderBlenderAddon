from .base import PropertyBase
from bpy.props import *
import bpy


class MeshProperties(PropertyBase):
    ''' Properties for mesh '''

    def sync(self, context):
        ''' sync the mesh '''
        mesh = self.id_data
        print("Syncing Mesh %s " % mesh.name)


classes = (MeshProperties,)
