from . import RPR_Panel


class RPR_CAMERA_PT_motion_blur(RPR_Panel):
    bl_label = "Motion Blur"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.camera and super().poll(context)

    def draw_header(self, context):
        self.layout.prop(context.scene.render, 'use_motion_blur', text="")

    def draw(self, context):
        self.layout.use_property_split = True
        col = self.layout.column()
        col.enabled = context.scene.render.use_motion_blur
        col.prop(context.camera.rpr, 'motion_blur_exposure', slider=True)


class RPR_CAMERA_PT_dof(RPR_Panel):
    bl_label = "Depth of Field"
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return context.camera and super().poll(context)

    def draw_header(self, context):
        self.layout.prop(context.camera.dof, "use_dof", text="")

    def draw(self, context):
        dof = context.camera.dof

        layout = self.layout
        layout.use_property_split = True
        layout.active = dof.use_dof

        split = layout.split()

        col = split.column()
        col.prop(dof, "focus_object", text="Focus Object")

        sub = col.row()
        sub.active = dof.focus_object is None
        sub.prop(dof, "focus_distance", text="Distance")


class RPR_CAMERA_PT_dof_aperture(RPR_Panel):
    bl_label = "Aperture"
    bl_parent_id = "RPR_CAMERA_PT_dof"

    def draw(self, context):
        dof = context.camera.dof

        layout = self.layout
        layout.use_property_split = True
        layout.active = dof.use_dof

        col = layout.column()
        col.prop(dof, "aperture_fstop")
        col.prop(dof, "aperture_blades")
