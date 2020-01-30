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
        """ Load image, put on current light and force light object update in viewport """
        context.light.rpr.ies_file = load_image(self.filepath)

        # force scene depsgraph to update light object
        energy = context.light.energy
        context.light.energy = 0.0
        context.light.energy = energy

        return {'FINISHED'}
