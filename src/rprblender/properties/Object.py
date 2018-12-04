from .base import PropertyBase, PanelBase
from bpy.props import *
import bpy


class ObjectProperties(PropertyBase):
    ''' Properties for objects '''

    camera_visible : BoolProperty(name='Camera Visibility', default=True)

    def sync(self, context):
        ''' sync the object and any data attached '''
        obj = self.id_data
        print("Syncing object %s " % obj.name)

        if self.camera_visible and hasattr(obj.data, 'rpr'):
            obj.data.rpr.sync(context)




class RPR_OBJECT_PT_object(PanelBase):
    ''' panel to display above properties '''
    bl_idname = "object_PT_property_example"
    bl_label = "RPR Property Example"
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object and super().poll(context)

    def draw(self, context):
        if context.object:
            rpr = context.object.rpr
            self.layout.prop(rpr, "camera_visible")



# I think this could be automated a bit more so less boilerplate is written 
# similar to @rpraddon.register_class
def register():
    from bpy.utils import register_class
    register_class(ObjectProperties)
    register_class(RPR_OBJECT_PT_object)

    bpy.types.Object.rpr = PointerProperty(type=ObjectProperties)

def unregister():
    from bpy.utils import unregister_class
    unregister_class(RPR_OBJECT_PT_object)
    unregister_class(ObjectProperties)
