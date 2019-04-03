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


class DATA_PT_RPR_camera_dof_aperture(RPR_Panel):
    bl_label = "Aperture"
    bl_parent_id = "DATA_PT_camera_dof"
    
    @classmethod
    def poll(cls, context):
        return context.camera and RPR_Panel.poll(context)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True

        cam = context.camera
        dof_options = cam.gpu_dof

        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)

        col = flow.column()
        col.prop(dof_options, "fstop")
        col.prop(dof_options, "blades")

