import bpy
from bpy.props import (
    BoolProperty,
    FloatVectorProperty,
    FloatProperty,
    StringProperty,
    EnumProperty,
    PointerProperty,
)

from rprblender.utils.world import IBL_LIGHT_NAME, calculate_rotation_matrix, create_environment_image
from rprblender.utils import logging
from . import RPR_Properties


log = logging.Log(tag='World')


class RPR_EnvironmentProperties(RPR_Properties):
    """World environment light and overrides settings"""
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

    # ibl
    ibl_type: EnumProperty(
        name="IBL Type",
        items=(('COLOR', "Color", "Use solid color for lighting"),
               ('IBL', "IBL Map", "Use IBL Map for lighting"),
               ),
        description="IBL Type",
        default='COLOR',
    )
    ibl_color: FloatVectorProperty(
        name='Color',
        description="Color to use when as a constant environment light",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    ibl_intensity: FloatProperty(
        name="Intensity",
        description="Intensity",
        min=0.0, default=1.0,
    )
    ibl_image: PointerProperty(
        type=bpy.types.Image
    )

    # sun and sky

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
        if self.enabled:
            if self.light_type == 'IBL':
                # single rotation gizmo is used by IBL and environment overrides
                if self.gizmo:
                    self.update_gizmo(None)
                matrix = calculate_rotation_matrix(self.gizmo_rotation)

                self.sync_ibl(rpr_context, matrix)

    def sync_ibl(self, rpr_context, matrix):
        # TODO As soon as portal light type ready support it here
        # for obj_key in self.portal_lights_meshes:
        #     ibl.attach_portal(self.core_scene, self.get_synced_obj(obj_key).core_obj)

        image = create_environment_image(rpr_context, self.ibl_type, self.ibl_color, self.ibl_image)

        ibl = rpr_context.create_light(IBL_LIGHT_NAME, 'environment')
        ibl.set_group_id(0)

        ibl.set_image(image)
        ibl.set_intensity_scale(self.ibl_intensity)
        ibl.set_transform(matrix, False)

        rpr_context.scene.attach(ibl)

    def sync_update(self, rpr_context, old_settings, new_settings):
        if old_settings.enabled != new_settings.enabled:
            if self.enabled:
                self.sync(rpr_context)
            else:
                rpr_context.remove_object(IBL_LIGHT_NAME)
                rpr_context.remove_image(IBL_LIGHT_NAME)
            return

        ibl = rpr_context.objects[IBL_LIGHT_NAME]

        if old_settings.ibl_color != new_settings.ibl_color or \
                old_settings.ibl_image != new_settings.ibl_image or \
                old_settings.ibl_type != new_settings.ibl_type:
            rpr_context.remove_image(IBL_LIGHT_NAME)
            image = create_environment_image(rpr_context, self.ibl_type, self.ibl_color, self.ibl_image)
            ibl.set_image(image)

        if old_settings.ibl_intensity != new_settings.ibl_intensity:
            ibl.set_intensity_scale(self.ibl_intensity)

        if old_settings.gizmo_rotation != new_settings.gizmo_rotation:
            if self.gizmo:
                self.update_gizmo(None)
            matrix = calculate_rotation_matrix(self.gizmo_rotation)
            ibl.set_transform(matrix, False)

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
