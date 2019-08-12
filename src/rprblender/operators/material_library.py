import bpy
from . import RPR_Operator
from rprblender import material_library

from rprblender.utils.logging import Log
log = Log(tag='operator.material_library')


class RPR_MATERIAL_LIBRARY_OP_import_material(RPR_Operator):
    bl_idname = "rpr.import_material_operator"
    bl_label = "Import Material"
    bl_description = "Import selected material"

    @classmethod
    def poll(cls, context):
        return super().poll(context) and material_library.rpr_material_library and context.object

    # Perform the operator action.
    def execute(self, context):
        library = material_library.rpr_material_library
        if not library or not library.is_valid:
            return {'FINISHED'}

        properties = context.window_manager.rpr_material_library_properties

        material_id = properties.materials

        # check if library have anything to import
        if material_id:
            xml_path, material_name = library.get_material_xml(material_id)
            material_library.import_xml_material(context.material, material_name, xml_path, properties.copy_textures)

            # arrange nodes assuming RPR Uber and RPR Math nodes sizes
            bpy.ops.rpr.arrange_material_nodes(margin_vertical=250, margin_horizontal=350)
        return {'FINISHED'}
