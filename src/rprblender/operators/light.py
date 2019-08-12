import bpy
from bpy_extras.io_utils import ImportHelper
from bpy_extras.image_utils import load_image

from . import RPR_Operator


class RPR_LIGHT_OP_open_IES_file(RPR_Operator, ImportHelper):
    bl_idname = 'rpr.open_ies_file'
    bl_label = "Open IES file"
    bl_description = "Open IES file"

    filename_ext = '.ies'

    filter_glob: bpy.props.StringProperty(
        default='*.ies',
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        context.light.rpr.ies_file = load_image(self.filepath)
        return {'FINISHED'}
