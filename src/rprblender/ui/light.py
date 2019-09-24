from . import RPR_Panel


class RPR_LIGHT_PT_light(RPR_Panel):
    """
    Physical light sources
    """
    bl_label = "Light"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.light and super().poll(context)

    def draw(self, context):
        layout = self.layout

        light = context.light
        rpr_light = light.rpr

        layout.prop(light, "type", expand=True)

        layout.use_property_split = True
        layout.use_property_decorate = False

        main_col = layout.column()
        if light.type == 'POINT':
            row = main_col.row(align=True)
            row.template_ID(rpr_light, "ies_file", open="rpr.open_ies_file")

        elif light.type == 'SPOT':
            col = main_col.column(align=True)
            col.prop(light, 'spot_size', slider=True)
            col.prop(light, 'spot_blend', slider=True)

            main_col.prop(light, 'show_cone')

        elif light.type == 'SUN':
            main_col.prop(rpr_light, 'shadow_softness')

        elif light.type == 'AREA':
            main_col.prop(rpr_light, 'shape')

            if rpr_light.shape == 'MESH':
                main_col.prop(rpr_light, 'mesh')

            elif rpr_light.shape in ('RECTANGLE', 'ELLIPSE'):
                col = main_col.column(align=True)
                col.prop(light, 'size', text="Size X")
                col.prop(light, 'size_y', text="Y")

            else:
                main_col.prop(light, 'size')

            col = main_col.column(align=True)
            col.prop(rpr_light, 'visible')
            row = col.row()
            row.enabled = rpr_light.visible
            row.prop(rpr_light, 'cast_shadows')

            row = col.row()
            row.active = context.scene.render.use_motion_blur
            row.prop(context.object.rpr, "motion_blur")

        main_col.separator()
        main_col.row(align=True).prop(light.rpr, 'group')


class RPR_LIGHT_PT_intensity(RPR_Panel):
    """
    Physical light intensity
    """
    bl_label = "Intensity & Color"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.light and context.light.type in ('POINT', 'SPOT', 'SUN', 'AREA') and super().poll(context)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        light = context.light
        rpr_light = light.rpr

        main_col = layout.column()
        if light.type in ('POINT', 'SPOT'):
            intensity_units = 'intensity_units_point'
        elif light.type == 'SUN':
            intensity_units = 'intensity_units_dir'
        else:
            intensity_units = 'intensity_units_area'
        main_col.prop(rpr_light, intensity_units)

        col = main_col.column(align=True)
        
        if getattr(rpr_light, intensity_units) == 'DEFAULT':
            col.prop(light, 'energy')
        else:
            col.prop(rpr_light, 'intensity')

        if getattr(rpr_light, intensity_units) in ('WATTS', 'RADIANCE'):
            col.prop(rpr_light, 'luminous_efficacy', slider=True)
        elif light.type == 'AREA' and getattr(rpr_light, intensity_units) == 'DEFAULT':
            col.prop(rpr_light, 'intensity_normalization')

        main_col.separator()
        main_col.prop(light, 'color')

        col = main_col.column(align=True)
        col.prop(rpr_light, 'use_temperature')
        row = col.row()
        row.enabled = rpr_light.use_temperature
        row.prop(rpr_light, 'temperature', slider=True)

        if light.type == 'AREA':
            main_col.template_ID(rpr_light, "color_map", open="image.open")
