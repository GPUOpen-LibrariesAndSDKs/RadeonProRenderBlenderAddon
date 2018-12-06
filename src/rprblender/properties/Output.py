import bpy
from bpy.types import PointerProperty

from .base import RPR_Property, RPR_Panel
from rprblender import logging


class RPR_OutputSettings(RPR_Property):
    @classmethod
    def register(cls):
        bpy.types.Scene.rpr = PointerProperty(
            name="RPR Render Settings",
            description="RPR render settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        del bpy.types.Scene.rpr


class RPR_PT_OutputPanel(RPR_Panel, bpy.types.Panel):
    bl_idname = "RPR_PT_render_properties"
    bl_label = "RPR Render Properties"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.row().prop(scene.render, "resolution_x")
        layout.row().prop(scene.render, "resolution_y")

        layout.row().prop(scene, "frame_start")
        layout.row().prop(scene, "frame_end")
        layout.row().prop(scene, "frame_step")
        layout.row().prop(scene.render, "fps")


classes = (RPR_PT_OutputPanel,)
