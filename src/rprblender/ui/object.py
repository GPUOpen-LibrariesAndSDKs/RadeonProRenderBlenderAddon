from . import RPR_Panel


class RPR_OBJECT_PT_object(RPR_Panel):
    bl_label = "RPR Settings"
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object and \
               context.object.type in ('MESH', 'CURVE', 'FONT', 'SURFACE', 'META') and \
               super().poll(context)

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr = context.object.rpr

        self.layout.prop(rpr, 'shadowcatcher')
        self.layout.prop(rpr, 'reflection_catcher')
        self.layout.prop(rpr, 'portal_light')
        col = self.layout.column()
        col.active = context.scene.render.use_motion_blur
        col.prop(rpr, "motion_blur")


class RPR_OBJECT_PT_visibility(RPR_Panel):
    bl_label = "Visibility"
    bl_parent_id = 'RPR_OBJECT_PT_object'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr = context.object.rpr

        flow = self.layout.grid_flow(row_major=True, even_columns=True)
        flow.column().prop(rpr, 'visibility_in_primary_rays')
        flow.column().prop(rpr, 'reflection_visibility')
        flow.column().prop(rpr, 'refraction_visibility')
        flow.column().prop(rpr, 'diffuse_visibility')
        flow.column().prop(rpr, 'shadows')


class RPR_OBJECT_PT_subdivision(RPR_Panel):
    bl_label = "Subdivision"
    bl_parent_id = 'RPR_OBJECT_PT_object'

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
