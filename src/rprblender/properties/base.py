''' property classes should be self contained.  They may include:
	PropertyGroup class
		with properties that can be attached to a blender ID type
		methods for syncing these properties
	And panel classes for displaying these properties

	The idea here is to keep all the properties syncing, data, display etc in one place.  
	Basically a "model/view" type pattern where we bring them together for ease of maintenance.  
	Slightly inspired by vue.js

	TODO could we use decorators to register???
'''

import bpy
import pyrpr


class PropertyBase(bpy.types.PropertyGroup):
	def sync(self, parent, context: pyrpr.Context):
		''' Sync will update this object in the context.  
			And call any sub-objects that need to be synced  
			rpr_context object in the binding will be the only place we keep 
			"lists of items synced." '''
		pass


class PanelBase(bpy.types.Panel):
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    COMPAT_ENGINES = {'RPR'}

    @classmethod
    def poll(cls, context):
        return context.engine in cls.COMPAT_ENGINES
