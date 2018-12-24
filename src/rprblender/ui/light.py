from . import RPR_Panel


class RPR_LIGHT_PT_light(RPR_Panel):
    """
    Physical light sources
    """
    bl_label = "RPR Settings"
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return context.light and RPR_Panel.poll(context)

    def draw(self, context):
        layout = self.layout

        light = context.light

        layout.prop(light, "type", expand=True)

        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.row().prop(light, 'color')
        layout.row().prop(light.rpr, 'use_temperature')
        row = layout.row()
        row.enabled = light.rpr.use_temperature
        row.prop(light.rpr, 'temperature', slider=True)

        layout.separator()
        layout.row().prop(light.rpr, 'intensity')
        if light.type in ('POINT', 'SPOT'):
            intensity_units = 'intensity_units_point'
        elif light.type == 'SUN':
            intensity_units = 'intensity_units_dir'
        else:
            intensity_units = 'intensity_units_area'
        layout.row().prop(light.rpr, intensity_units, text="Units")
        if getattr(light.rpr, intensity_units) in ('WATTS', 'RADIANCE'):
            layout.row().prop(light.rpr, 'luminous_efficacy', slider=True)
        elif light.type == 'AREA' and getattr(light.rpr, intensity_units) == 'DEFAULT':
            layout.row().prop(light.rpr, 'intensity_normalization')

        layout.separator()
        if light.type == 'SPOT':
            layout.prop(light, 'spot_size', text="Angle", slider=True)
            layout.row().prop(light, 'spot_blend', text="Falloff", slider=True)
        elif light.type == 'AREA':
            layout.prop(light.rpr, 'shape', text='Shape')
            layout.row().prop(light, 'size', text="Size X")  # , slider=True)
            layout.row().prop(light, 'size_y', text="Size Y")  # , slider=True)
        elif light.type == 'SUN':
            layout.prop(light.rpr, 'shadow_softness')
        elif light.type == 'POINT':
            col = layout.column(align=True)
            col.label(text='IES Data File:')

            row = col.row(align=True)
            row.alignment = 'EXPAND'
            row.prop(light.rpr, "ies_file_name", text='')
            if light.rpr.ies_file_name:
                row.operator('rpr.light_op_remove_ies_data', text='', icon='X')
            else:
                row.operator('rpr.light_op_select_ies_data', text='', icon='FILE_FOLDER')

        layout.separator()
        layout.prop(light, 'use_shadow')
        layout.row(align=True).prop(light.rpr, 'group')

