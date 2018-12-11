import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from . import RPR_Properties, RPR_Panel
from rprblender import logging


class RPR_RenderDeviceProperties(RPR_Properties):
    use_cpu: BoolProperty(default=False)
    use_gpu: BoolProperty(default=True)

    motion_blur: BoolProperty(
        name="Motion Blur", description="Enable Motion Blur",
        default=False,
    )


class RPR_RenderProperties(RPR_Properties):
    render: PointerProperty(type=RPR_RenderDeviceProperties)

    def sync(self, context):
        scene = self.id_data
        print("Syncing scene: %s" % scene.name)

        rpr_scene = context().create_scene()
        context().set_scene(rpr_scene)

        for obj in scene.objects:
            obj.rpr.sync(context)

    @classmethod
    def register(cls):
        logging.info("register", tag='Scene')
        bpy.types.Scene.rpr = PointerProperty(
            name="RPR Render Settings",
            description="RPR render settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        logging.info("unregister", tag='Scene')
        del bpy.types.Scene.rpr


class RPR_RENDER_PT_devices(RPR_Panel):
    bl_idname = 'rpr_render_PT_devices'
    bl_label = "RPR Final Render Device Settings"
    bl_context = 'render'

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        render = scene.rpr.render

        layout.row().prop(render, 'use_cpu')
        layout.row().prop(render, 'use_gpu')


classes_to_register = (RPR_RenderDeviceProperties, RPR_RenderProperties, RPR_RENDER_PT_devices)
