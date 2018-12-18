import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

import pyrpr
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

    def sync(self, rpr_context):
        scene = self.id_data
        logging.info("Syncing scene: %s" % scene.name)

        rpr_context.init(False, scene.render.resolution_x, scene.render.resolution_y, pyrpr.CREATION_FLAGS_ENABLE_GPU0)
        rpr_context.scene.set_name(scene.name)

        for obj in scene.objects:
            obj.rpr.sync(rpr_context)

        rpr_context.scene.set_camera(rpr_context.objects[scene.camera.name])
        rpr_context.enable_aov(pyrpr.AOV_COLOR)
        # TODO: setup other AOVs, image filters, shadow catcher

        # set default ray depth values
        depth = 5
        depth_diffuse = 2
        depth_glossy = 3
        depth_shadow = 3
        depth_refraction = 3
        depth_glossy_refraction = 3

        rpr_context.set_parameter("maxRecursion", depth)
        rpr_context.set_parameter("maxdepth.diffuse", depth_diffuse)
        rpr_context.set_parameter("maxdepth.glossy", depth_glossy)
        rpr_context.set_parameter("maxdepth.shadow", depth_shadow)
        rpr_context.set_parameter("maxdepth.refraction", depth_refraction)
        rpr_context.set_parameter("maxdepth.refraction.glossy", depth_glossy_refraction)

        scene.world.rpr.sync(rpr_context)

    @classmethod
    def register(cls):
        logging.info("Register", tag='Scene')
        bpy.types.Scene.rpr = PointerProperty(
            name="RPR Render Settings",
            description="RPR render settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        logging.info("Unregister", tag='Scene')
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
