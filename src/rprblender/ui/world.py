import bpy

from . import RPR_Panel


class RPR_WORLD_PT_environment(RPR_Panel):
    bl_label = "Environment Light"
    bl_space_type = "PROPERTIES"
    bl_context = 'world'

    @classmethod
    def poll(cls, context):
        return super().poll(context)  # and context.scene.world.rpr

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        environment = scene.world.rpr

        layout.enabled = environment.enabled

        # Environment
        layout.row().prop(environment, 'light_type', expand=True)
        if environment.light_type == 'IBL':
            self.draw_ibl(layout, environment)
        else:
            self.draw_sun_sky(layout, environment)

        self.draw_environment_gizmo(layout.column(), context, environment)

    def draw_ibl(self, layout, environment):
        box = layout.box()
        box.row().prop(environment, 'ibl_type', expand=True)

        col = box.column()
        col.use_property_split = True
        col.use_property_decorate = False

        if environment.ibl_type == 'COLOR':
            col.prop(environment, 'ibl_color')
            col.prop(environment, 'ibl_intensity')
        else:
            col.template_ID(environment, "ibl_image", open="image.open")
            col.prop(environment, 'ibl_intensity')

    def draw_sun_sky(self, layout, environment):
        layout.label(text="Under construction")

    def draw_header(self, context):
        self.layout.prop(context.scene.world.rpr, 'enabled', text="")

    def draw_environment_gizmo(self, column, context, environment):
        box = column.box()
        column1, column2, is_row = self.create_ui_autosize_column(context, box)
        column1.label(text='Object:')
        row = column1.row(align=True)
        row.prop_search(environment, 'gizmo', bpy.data, 'objects', text='')
        if not environment.gizmo:
            gizmo = row.operator("rpr.op_create_environment_gizmo", icon='ZOOM_IN', text="")
            if gizmo:
                gizmo.rotation = environment.gizmo_rotation
        column2.prop(environment, 'gizmo_rotation')


class RPR_WORLD_PT_overrides(RPR_Panel):
    bl_label = "Overrides"
    bl_parent_id = 'RPR_WORLD_PT_environment'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        def draw_override_section(data_type_name, data_type, color_name, image_name):
            # For each override show type selector and color/image input.
            box = self.layout.box()
            row = box.row()
            row.alignment = 'EXPAND'
            row.prop(environment, data_type_name, expand=True)
            row = box.row()
            row.alignment = 'EXPAND'
            if data_type == 'IMAGE':
                row.template_ID(environment, image_name, open="image.open")
            else:
                row.prop(environment, color_name)

        environment = context.scene.world.rpr

        self.layout.enabled = environment.enabled

        self.layout.prop(environment, 'override_background')
        if environment.override_background:
            draw_override_section('background_type', environment.background_type,
                                  'background_color', 'background_image')

        self.layout.prop(environment, 'override_reflection')
        if environment.override_reflection:
            draw_override_section('reflection_type', environment.reflection_type,
                                  'reflection_color', 'reflection_image')

        self.layout.prop(environment, 'override_refraction')
        if environment.override_refraction:
            draw_override_section('refraction_type', environment.refraction_type,
                                  'refraction_color', 'refraction_image')

        self.layout.prop(environment, 'override_transparency')
        if environment.override_transparency:
            draw_override_section('transparency_type', environment.transparency_type,
                                  'transparency_color', 'transparency_image')
