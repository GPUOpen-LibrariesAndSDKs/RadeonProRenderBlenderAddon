import math

import bpy
from bpy.props import (
    BoolProperty,
    FloatProperty,
    PointerProperty,
    IntProperty,
    EnumProperty,
)

import pyrpr
from . import RPR_Properties
from rprblender import utils

from rprblender.utils import logging
log = logging.Log(tag='Object')


class RPR_ObjectProperites(RPR_Properties):
    """
    Properties for objects
    """

    visibility_in_primary_rays: BoolProperty(
        name="Camera Visibility",
        description="This object will be visible in camera rays",
        default=True,
    )
    reflection_visibility: BoolProperty(
        name="Reflections Visibility",
        description="This object will be visible in reflections",
        default=True,
    )
    shadows: BoolProperty(
        name="Casts Shadows",
        description="This object will cast shadows",
        default=True,
    )
    shadowcatcher: BoolProperty(
        name="Shadow Catcher",
        description="Use this object as a shadowcatcher",
        default=False,
    )

    motion_blur: BoolProperty(
        name="Motion Blur",
        description="Enable Motion Blur",
        default=True,
    )
    motion_blur_scale: FloatProperty(
        name="Scale",
        description="Motion Blur Scale",
        default=1.0,
        min=0,
    )

    subdivision: BoolProperty(
        name="Subdivision",
        description="Enable subdivision",
        default=False,
    )
    subdivision_factor: FloatProperty(
        name="Adaptive Level",
        description="Subdivision factor for mesh, in pixels that it should be subdivided to. For finer subdivision set lower.",
        min=0.0, soft_max=10,
        default=1.0
    )
    subdivision_boundary_type: EnumProperty(
        name="Boundary Type",
        description="Subdivision boundary type",
        items=(
            ('EDGE_CORNER', "Edge and Corner", "Edge and corner"),
            ('EDGE', "Edge only", "Edge only")
        ),
        default='EDGE_CORNER',
    )
    subdivision_crease_weight: FloatProperty(
        name="Crease Weight",
        description="Subdivision crease weight",
        min=0.0,
        default=1.0,
    )

    def sync(self, rpr_context, obj_instance):
        ''' sync the object and any data attached '''
        obj = self.id_data

        log("Syncing object", obj)

        if obj.type in ['MESH', 'CAMERA', 'LIGHT']:
            obj.data.rpr.sync(rpr_context, obj_instance)

    def sync_update(self, rpr_context, is_updated_geometry, is_updated_transform):
        obj = self.id_data

        if obj.type not in ('MESH', 'LIGHT'):
            return False

        log("Updating object: {}, type={}, geometry={}, transform={}".format(obj, obj.type, is_updated_geometry, is_updated_transform))

        return obj.data.rpr.sync_update(rpr_context, obj, is_updated_geometry, is_updated_transform)

    @classmethod
    def register(cls):
        log("Register")
        bpy.types.Object.rpr = PointerProperty(
            name="RPR Object Settings",
            description="RPR Object settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Unregister")
        del bpy.types.Object.rpr
