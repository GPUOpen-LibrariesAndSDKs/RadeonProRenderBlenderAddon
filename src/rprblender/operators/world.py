import bpy

from . import RPR_Operator
from rprblender.utils import logging


class RPR_WORLD_OT_convert_cycles_environment(RPR_Operator):
    bl_idname = 'rpr.convert_cycles_environment'
    bl_label = "Convert Cycles Environment lightning settings"

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return super().poll(context) and context.scene.world

    def execute(self, context: bpy.types.Context):
        logging.info("Converting Cycles environment settings {}".format(context))

        return {'FINISHED'}


class RPR_WORLD_OP_create_environment_gizmo(bpy.types.Operator):
    bl_idname = "rpr.op_create_environment_gizmo"
    bl_label = "Create Environment Gizmo"

    rotation: bpy.props.FloatVectorProperty(
        name='Rotation', description='Rotation',
        subtype='EULER', size=3,
    )
    object_name: str = 'EnvObject'
    collection_name: str = 'SupportObjectsCollection'

    def execute(self, context):
        obj = bpy.data.objects.new(self.object_name, None)
        obj.empty_display_size = 3.0
        obj.empty_display_type = 'PLAIN_AXES'
        obj.location = (0, 0, 0)

        rpr_collection = context.scene.collection.children.get(self.collection_name)
        if not rpr_collection:
            rpr_collection = bpy.data.collections.new(self.collection_name)
            context.scene.collection.children.link(rpr_collection)
        rpr_collection.objects.link(obj)

        obj.rotation_euler = self.rotation

        context.scene.world.rpr.gizmo = obj
        return {'FINISHED'}
