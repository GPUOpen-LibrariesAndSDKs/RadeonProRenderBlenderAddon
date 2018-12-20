from . import RPR_Panel


class RPR_OBJECT_PT_object(RPR_Panel):
    bl_label = "RPR Settings"
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and super().poll(context)

    def draw(self, context):
        if context.object:
            rpr = getattr(context.object, 'rpr', None)
            if rpr and context.object.type == 'MESH':
                self.layout.row().prop(rpr, 'visibility_in_primary_rays')
                self.layout.row().prop(rpr, 'reflection_visibility')
                self.layout.row().prop(rpr, 'shadows')
                self.layout.row().prop(rpr, 'shadowcatcher')


class RPR_OBJECT_PT_motion_blur(RPR_Panel):
    bl_label = "RPR Motion Blur"
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and super().poll(context)

    def draw(self, context):
        self.layout.active = context.object.rpr.motion_blur
        rpr = getattr(context.object, 'rpr', None)
        if rpr and context.object.type == 'MESH':
            self.layout.row().prop(rpr, 'motion_blur_scale')

    def draw_header(self, context):
        self.layout.prop(context.object.rpr, "motion_blur", text="")
