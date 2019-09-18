from . import RPR_Panel


class RPR_WORLD_PT_environment(RPR_Panel):
    bl_label = "Environment Light"
    bl_space_type = "PROPERTIES"
    bl_context = 'world'

    def draw_header(self, context):
        self.layout.prop(context.scene.world.rpr, 'enabled', text="")

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        rpr = context.scene.world.rpr

        layout.enabled = rpr.enabled

        layout.prop(rpr, 'intensity')
        layout.separator()

        row = layout.row()
        row.use_property_split = False
        row.prop(rpr, 'mode', expand=True)

        if rpr.mode == 'IBL':
            ibl = rpr.ibl

            layout.template_ID(ibl, "image", open="image.open")

            row = layout.row()
            row.enabled = ibl.image is None
            row.prop(ibl, 'color')

        else:
            sun_sky = rpr.sun_sky

            col = layout.column(align=True)
            col.prop(sun_sky, 'azimuth')
            col.prop(sun_sky, 'altitude')

            layout.prop(sun_sky, 'resolution')


class RPR_EnvironmentOverride(RPR_Panel):
    bl_parent_id = 'RPR_WORLD_PT_environment'
    bl_options = {'DEFAULT_CLOSED'}

    type = ''

    def draw_header(self, context):
        rpr = context.scene.world.rpr
        row = self.layout.row()
        row.enabled = rpr.enabled
        row.prop(rpr, f'{self.type}_override', text="")

    def draw(self, context):
        rpr = context.scene.world.rpr

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.enabled = rpr.enabled and getattr(rpr, f'{self.type}_override')

        layout.template_ID(rpr, f'{self.type}_image', open='image.open')

        row = layout.row()
        row.enabled = getattr(rpr, f'{self.type}_image') is None
        row.prop(rpr, f'{self.type}_color')


class RPR_WORLD_PT_background_override(RPR_EnvironmentOverride):
    bl_label = "Background Override"
    type = 'background'

    def draw(self, context):
        rpr = context.scene.world.rpr
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.enabled = rpr.background_override

        row = layout.row()
        row.use_property_split = False
        row.prop(rpr, 'background_image_type', expand=True)

        layout.template_ID(rpr, 'background_image', open='image.open', new='image.new')
        
        row = layout.row()
        row.enabled = rpr.background_image is None
        row.prop(rpr, 'background_color')


class RPR_WORLD_PT_reflection_override(RPR_EnvironmentOverride):
    bl_label = "Reflection Override"
    type = 'reflection'


class RPR_WORLD_PT_refraction_override(RPR_EnvironmentOverride):
    bl_label = "Refraction Override"
    type = 'refraction'


class RPR_WORLD_PT_transparency_override(RPR_EnvironmentOverride):
    bl_label = "Transparency Override"
    type = 'transparency'


class RPR_WORLD_PT_gizmo(RPR_Panel):
    bl_label = "Gizmo"
    bl_parent_id = 'RPR_WORLD_PT_environment'

    def draw(self, context):
        rpr = context.scene.world.rpr

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.enabled = rpr.enabled

        layout.prop(rpr, 'gizmo_rotation')


class RPR_WORLD_PT_sun_sky(RPR_Panel):
    bl_label = "Sun & Sky Properties"
    bl_parent_id = 'RPR_WORLD_PT_environment'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return super().poll(context) and context.scene.world.rpr.mode == 'SUN_SKY'

    def draw(self, context):
        rpr = context.scene.world.rpr
        sun_sky = rpr.sun_sky

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.enabled = rpr.enabled

        flow = layout.grid_flow(row_major=True, even_columns=True)

        col = flow.column(align=True)
        col.prop(sun_sky, 'turbidity')
        col.prop(sun_sky, 'sun_glow')
        col.prop(sun_sky, 'sun_disc')

        col = flow.column(align=True)
        col.prop(sun_sky, 'saturation')
        col.prop(sun_sky, 'horizon_height')
        col.prop(sun_sky, 'horizon_blur')

        col = flow.column(align=True)
        col.prop(sun_sky, 'filter_color')
        col.prop(sun_sky, 'ground_color')
