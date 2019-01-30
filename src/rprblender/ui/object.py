from . import RPR_Panel


class RPR_OBJECT_PT_object(RPR_Panel):
    bl_label = "RPR Settings"
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and super().poll(context)

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr = context.object.rpr
        flow = self.layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        flow.column().prop(rpr, 'visibility_in_primary_rays')
        flow.column().prop(rpr, 'reflection_visibility')
        flow.column().prop(rpr, 'shadows')
        flow.column().prop(rpr, 'shadowcatcher')


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


class RPR_OBJECT_PT_subdivision(RPR_Panel):
    bl_label = "Subdivision"
    bl_parent_id = 'RPR_OBJECT_PT_object'

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and super().poll(context)

    def draw_header(self, context):
        self.layout.prop(context.object.rpr, 'subdivision', text="")

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr = context.object.rpr

        col = self.layout.column()
        col.enabled = rpr.subdivision
        col.prop(rpr, 'subdivision_factor')
        col.prop(rpr, 'subdivision_crease_weight')
        col.prop(rpr, 'subdivision_boundary_type')
