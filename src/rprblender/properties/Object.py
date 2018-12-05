from .base import PropertyBase, PanelBase
import bpy


class ObjectProperties(PropertyBase):
    ''' Properties for objects '''

    camera_visible: bpy.props.BoolProperty(name='Camera Visibility', default=True)

    def sync(self, context):
        ''' sync the object and any data attached '''
        obj = self.id_data
        print("Syncing Object %s " % obj.name)

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
            rpr = getattr(context.object, 'rpr', None)
            self.layout.row().label(text="Just the test label")
            if rpr:
                self.layout.row().prop(rpr, "camera_visible")


classes = (ObjectProperties, RPR_OBJECT_PT_object)
