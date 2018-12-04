from .base import PropertyBase
from bpy.props import *
import bpy



class MeshProperties(PropertyBase):
	''' Properties for mesh '''
	
	def sync(self, context):
		''' sync the mesh '''
		mesh = self.id_data
		print("Syncing mesh %s " % mesh.name)


# I think this could be automated a bit more so less boilerplate is written
def register():
	from bpy.utils import register_class
	register_class(MeshProperties)

	bpy.types.Mesh.rpr = PointerProperty(type=MeshProperties)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(MeshProperties)