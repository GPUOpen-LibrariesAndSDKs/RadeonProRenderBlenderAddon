from . import RPR_Panel


class RPR_DATA_PT_mesh(RPR_Panel):
    bl_label = "RPR UV Maps"
    bl_parent_id = 'DATA_PT_uv_texture'

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False

        obj = context.object
        if obj.type != 'MESH':
            return False

        mesh = obj.data
        return len(mesh.uv_layers) > 1

    def draw(self, context):
        mesh = context.object.data

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        flow = layout.split(factor=0.5)
        col1 = flow.column()
        col2 = flow.column()

        col1.label(text="       Primary:")
        col1.label(text="       Secondary:")

        col2.label(text=mesh.rpr.primary_uv_layer.name)
        col2.prop_search(mesh.rpr, 'secondary_uv_layer_name', mesh, 'uv_layers', text="")
