from . import Object #could this be automated a bit?
from . import Mesh

def register():
	Object.register()
	Mesh.register()

def unregister():
	Object.unregister()
	Mesh.unregister()