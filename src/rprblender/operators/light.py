import bpy
from bpy_extras.io_utils import ExportHelper


class RPR_LIGHT_OP_select_ies_data(bpy.types.Operator, ExportHelper):
    bl_idname = "rpr.light_op_select_ies_data"
    bl_label = "Load IES Light Data"

    filename_ext: str = ".ies"

    filter_glob: bpy.props.StringProperty(
        default="*.ies",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        context.light.rpr.ies_file_name = self.filepath
        return {'FINISHED'}


class RPR_LIGHT_OP_remove_ies_data(bpy.types.Operator):
    bl_idname = "rpr.light_op_remove_ies_data"
    bl_label = "Disconnect IES Light Data"

    def execute(self, context):
        context.light.rpr.ies_file_name = ""
        return {'FINISHED'}
