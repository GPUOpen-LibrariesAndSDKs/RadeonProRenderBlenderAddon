import bpy
import rprblender
from rprblender import config
from rprblender import rpraddon
from rprblender.nodes import RPRPanel
from rprblender import logging

from rprblender.converter.cycles_converter import CyclesMaterialConverter
from rprblender.converter.converter import log_convert


########################################################################################################################
# UI
########################################################################################################################

@rpraddon.register_class
class RPRConvertCyclesMaterialOperator(bpy.types.Operator):
    bl_idname = "rpr.convert_cycles_material"
    bl_label = "Convert Cycles Material"

    @classmethod
    def poll(cls, context):
        return context.active_object.active_material

    def execute(self, context):
        material = context.active_object.active_material
        converter = CyclesMaterialConverter()
        converter.convert(material)
        if converter.errors:
            self.report({'WARNING'}, "Conversion completed with errors.\n Please see the log for more details!")
        return {'FINISHED'}


@rpraddon.register_class
class RPRConvertAllCyclesMaterialsOperator(bpy.types.Operator):
    bl_idname = "rpr.convert_all_cycles_materials"
    bl_label = "Convert All Cycles Materials"

    @classmethod
    def poll(cls, context):
        return len(bpy.data.materials) > 0

    def execute(self, context):
        errors = []
        for mat in bpy.data.materials:
            log_convert('convert material: ', mat.name)
            converter = CyclesMaterialConverter()
            converter.convert(mat)
            if converter.error:
                errors.append(mat.name)
        if errors:
            logging.error("Materials failed to convert without errors:", *errors)
            self.report({'ERROR'}, "Conversion completed with errors.\n Please see the log for more details!")
        return {'FINISHED'}


class RPRMaterialConvertePanel(RPRPanel, bpy.types.Panel):
    bl_label = "RPR Converter"
    bl_context = "material"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.layout.operator('rpr.convert_cycles_material')
        self.layout.operator('rpr.convert_all_cycles_materials')


@rpraddon.register_class
class RPRMaterial_PT_converter(RPRMaterialConvertePanel):
    @classmethod
    def poll(cls, context):
        return RPRPanel.poll(context) and config.cycles_convert_enabled


@rpraddon.register_class
class RPRMaterial_PT_converter_in_view(RPRMaterialConvertePanel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.active_material and context.space_data.tree_type == 'RPRTreeType' \
               and RPRPanel.poll(context) and config.cycles_convert_enabled


@rpraddon.register_class
class RPRMaterial_PT_AxF(RPRPanel, bpy.types.Panel):
    bl_label = "RPR AxF"
    bl_context = "material"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.active_object.active_material and RPRPanel.poll(context)

    def draw(self, context):
        self.layout.operator('rpr.import_axf_material')
