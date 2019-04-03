from . import RPR_Panel


class RPR_VIEWLAYER_PT_aovs(RPR_Panel):
    bl_label = "RPR Passes"
    bl_context = 'view_layer'

    def draw(self, context):
        view_layer = context.view_layer.rpr

        row = self.layout.split(factor=0.5, align=True)

        col1 = row.column()
        col2 = row.column()
        for i in range(len(view_layer.enable_aovs)):
            aov = view_layer.aovs_info[i]
            if aov['name'] == "Combined":
                # not displaying "Combined" pass as it is always enabled by Blender
                continue

            if i <= len(view_layer.enable_aovs) // 2:
                col1.prop(view_layer, 'enable_aovs', index=i, text=aov['name'])
            else:
                col2.prop(view_layer, 'enable_aovs', index=i, text=aov['name'])


class RPR_RENDER_PT_denoiser(RPR_Panel):
    bl_label = "RPR Denoiser"
    bl_context = 'view_layer'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(context.view_layer.rpr.denoiser, 'enable', text="")

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        denoiser = context.view_layer.rpr.denoiser

        col = self.layout.column()
        col.enabled = denoiser.enable
        col.prop(denoiser, 'filter_type')

        if denoiser.filter_type == 'BILATERAL':
            col.prop(denoiser, "radius")
            col.prop(denoiser, 'color_sigma', slider=True)
            col.prop(denoiser, 'normal_sigma', slider=True)
            col.prop(denoiser, 'p_sigma', slider=True)
            col.prop(denoiser, 'trans_sigma', slider=True)
        elif denoiser.filter_type == 'EAW':
            col.prop(denoiser, 'color_sigma', slider=True)
            col.prop(denoiser, 'normal_sigma', slider=True)
            col.prop(denoiser, 'depth_sigma', slider=True)
            col.prop(denoiser, 'trans_sigma', slider=True)
        elif denoiser.filter_type == 'LWR':
            col.prop(denoiser, 'samples', slider=True)
            col.prop(denoiser, 'half_window', slider=True)
            col.prop(denoiser, 'bandwidth', slider=True)
        elif denoiser.filter_type == 'ML':
            pass
        else:
            raise TypeError("No such filter type: %s" % denoiser.filter_type)
