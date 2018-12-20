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

        scene = context.scene
        light = context.light

        layout.prop(light, "type", expand=True)
