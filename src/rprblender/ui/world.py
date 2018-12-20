import bpy

from . import RPR_Panel


class RPR_WORLD_PT_environment(RPR_Panel):
    bl_label = "RPR Environment Light"
    bl_space_type = "PROPERTIES"
    bl_context = 'world'

    @classmethod
    def poll(cls, context):
        return super().poll(context)  # and context.scene.world.rpr

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        environment = scene.world.rpr

        if context.scene.world.rpr.enabled:
            environment.draw(layout)
            self.draw_environment_gizmo(layout.column(), context)

    def draw_header(self, context):
        self.layout.prop(context.scene.world.rpr, 'enabled', text="")

    def draw_environment_gizmo(self, column, context):
        box = column.box()
        column1, column2, is_row = self.create_ui_autosize_column(context, box)
        column1.label(text='Object:')
        row = column1.row(align=True)
        row.prop_search(context.scene.world.rpr, 'gizmo', bpy.data, 'objects', text='')
        if not context.scene.world.rpr.gizmo:
            gizmo = row.operator("rpr.op_create_environment_gizmo", icon='ZOOM_IN', text="")
            if gizmo:
                gizmo.rotation = context.scene.world.rpr.gizmo_rotation
        column2.prop(context.scene.world.rpr, 'gizmo_rotation')
