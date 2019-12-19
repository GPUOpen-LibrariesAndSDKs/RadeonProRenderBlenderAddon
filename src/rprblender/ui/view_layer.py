import pyrpr

from . import RPR_Panel
from rprblender import utils

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

            col = col1 if i <= len(view_layer.enable_aovs) // 2 else col2
            r = col.row()
            r.prop(view_layer, 'enable_aovs', index=i, text=aov['name'])


class RPR_RENDER_PT_denoiser(RPR_Panel):
    bl_label = "RPR Denoiser"
    bl_context = 'view_layer'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(context.view_layer.rpr.denoiser, 'enable', text="")

    def draw(self, context):
        ''' if this is macOS and 2.81+ use the builtin Blender denoiser '''
        if utils.USE_BLENDER_DENOISER:
            if utils.has_denoise_node():
                self.layout.label(text="Denoiser activated in compositor.")
            else:
                self.layout.operator('rpr.add_denoiser_node', text="Enable Blender Denoiser")
        else:
            self.layout.use_property_split = True
            self.layout.use_property_decorate = False

            denoiser = context.view_layer.rpr.denoiser

            col = self.layout.column()
            col.enabled = denoiser.enable
            col.active = denoiser.is_available(context.scene)
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
                col.prop(denoiser, 'ml_color_only')

            else:
                raise TypeError("No such filter type: %s" % denoiser.filter_type)


class RPR_RENDER_PT_override(RPR_Panel):
    """ Display View Layer material Override from Cycles """
    bl_label = "Override"
    bl_options = {'DEFAULT_CLOSED'}
    bl_context = "view_layer"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        view_layer = context.view_layer

        layout.prop(view_layer, "material_override")
