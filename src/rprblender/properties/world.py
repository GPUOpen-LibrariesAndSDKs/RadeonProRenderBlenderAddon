import bpy
from bpy.props import (
    BoolProperty,
    FloatVectorProperty,
    FloatProperty,
    StringProperty,
    EnumProperty,
    PointerProperty,
)
import mathutils
import numpy as np

from rprblender import utils
from rprblender.utils import image as image_utils
from rprblender.utils import logging
from . import RPR_Properties


log = logging.Log(tag='World')


class RPR_WORLD_PROP_environment_ibl(RPR_Properties):
    bl_label = "RPR IBL Settings"

    ibl_type: EnumProperty(
        name="IBL Type",
        items=(('COLOR', "Color", "Use solid color for lighting"),
               ('IBL', "IBL Map", "Use IBL Map for lighting"),
               ),
        description="IBL Type",
        default='COLOR',
    )
    color: FloatVectorProperty(
        name='Color',
        description="Color to use when as a constant environment light",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    intensity: FloatProperty(
        name="Intensity",
        description="Intensity",
        min=0.0, default=1.0,
    )
    ibl_image: PointerProperty(
        type=bpy.types.Image
    )

    def sync(self, rpr_context):
        ibl = rpr_context.create_light('ENVIRONMENT', 'environment')
        ibl.set_group_id(0)

        # TODO As soon as portal light type ready support it here
        # for obj_key in self.portal_lights_meshes:
        #     ibl.attach_portal(self.core_scene, self.get_synced_obj(obj_key).core_obj)

        image = None
        if self.ibl_type == 'COLOR':
            image = image_utils.create_flat_color_image_data(rpr_context, 'Environment', (*self.color, 1))
        elif self.ibl_type == 'IBL':
            if self.ibl_image:
                try:
                    image = image_utils.get_rpr_image(rpr_context, utils.key(self.ibl_image), self.ibl_image)
                except ValueError as e:
                    log.error("Cant's read environment image: {}".format(e))

        if image:
            ibl.set_image(image)
            ibl.set_intensity_scale(self.intensity)
        else:  # Purple "ERROR" skies
            ibl.set_image(image_utils.create_flat_color_image_data(rpr_context, 'Environment', (1, 0, 1, 1)))

        rpr_context.scene.attach(ibl)
        return ibl

    def draw(self, layout):
        box = layout.box()
        box.row().prop(self, 'ibl_type', expand=True)
        if self.ibl_type == 'COLOR':
            box.row().prop(self, 'color')
            box.row().prop(self, 'intensity')
        else:
            box.row().template_ID(self, "ibl_image", open="image.open")
            box.row().prop(self, 'intensity')


class RPR_WORLD_PROP_environment_sun_sky(RPR_Properties):
    bl_label = "RPR Sun&Sky Settings"

    def sync(self, rpr_context):
        log("RPR_WORLD_PROP_environment_sun_sky.sync()")

    def draw(self, layout):
        layout.label(text="Under construction")


class RPR_WORLD_PROP_environment(RPR_Properties):
    bl_idname = "rpr_world_prop_environment"
    bl_label = "RPR Environment Settings"

    enabled: BoolProperty(default=True)
    # environment
    light_type: EnumProperty(
        name="IBL Type",
        items=(('IBL', "IBL Map", "Use IBL environment light"),
               ('SUN_SKY', "Sun & Sky", "Use Sun&Sky"),
               ),
        description="Environment light type",
        default='IBL',
    )
    ibl: PointerProperty(type=RPR_WORLD_PROP_environment_ibl)
    sun_sky: PointerProperty(type=RPR_WORLD_PROP_environment_sun_sky)
    # overrides

    # environment transform gizmo
    def update_gizmo_rotation(self, context):
        if self.gizmo in bpy.data.objects:
            obj = bpy.data.objects[self.gizmo]
            obj.rotation_euler = self.gizmo_rotation

    def update_gizmo(self, context):
        if self.gizmo in bpy.data.objects:
            obj = bpy.data.objects[self.gizmo]
            self['gizmo_rotation'] = obj.rotation_euler

    gizmo_rotation: bpy.props.FloatVectorProperty(
        name='Rotation', description='Rotation',
        subtype='EULER', size=3,
        update=update_gizmo_rotation
    )

    gizmo: bpy.props.StringProperty(
        name="Gizmo",
        description="Environment Helper",
        update=update_gizmo
    )

    def sync(self, rpr_context):
        log("Environment synchronization")
        if self.enabled:
            if self.light_type == 'IBL':
                ibl = self.ibl.sync(rpr_context)
                if self.gizmo:
                    self.update_gizmo(None)
                rotation = self.gizmo_rotation
                rotation_updated = (rotation[0], rotation[1], rotation[2] + np.pi)
                self.set_rotation(ibl, rotation_updated)

    @staticmethod
    def set_rotation(ibl, rotation_gizmo):
        rotation_gizmo = (-rotation_gizmo[0], -rotation_gizmo[1], -rotation_gizmo[2])
        euler = mathutils.Euler(rotation_gizmo)
        rotation_matrix = np.array(euler.to_matrix(), dtype=np.float32)
        fixup = np.array([[1, 0, 0],
                          [0, 0, 1],
                          [0, 1, 1]], dtype=np.float32)
        matrix = np.identity(4, dtype=np.float32)
        matrix[:3, :3] = np.dot(fixup, rotation_matrix)

        ibl.set_transform(matrix, False)

    def draw(self, layout):
        layout.row().prop(self, 'light_type', expand=True)
        if self.light_type == 'IBL':
            self.ibl.draw(layout)
        else:
            self.sun_sky.draw(layout)

    @classmethod
    def register(cls):
        log("Register")
        bpy.types.World.rpr = bpy.props.PointerProperty(
            name="RPR World Settings",
            description="RPR Environment Settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Unregister")
        del bpy.types.World.rpr
