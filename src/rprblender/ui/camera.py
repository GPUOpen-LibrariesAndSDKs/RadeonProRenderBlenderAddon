from . import RPR_Panel


class RPR_CAMERA_PT_motion_blur(RPR_Panel):
    bl_label = "Motion Blur"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.camera and RPR_Panel.poll(context)

    def draw_header(self, context):
        row = self.layout.row()
#        row.active = context.scene.rpr.render.motion_blur
        row.prop(context.camera.rpr, 'motion_blur', text='')

    def draw(self, context):
        self.layout.use_property_split = True
        row = self.layout.row()
#        row.active = context.scene.rpr.render.motion_blur
        row.enabled = context.camera.rpr.motion_blur
        row.prop(context.camera.rpr, 'motion_blur_exposure')
