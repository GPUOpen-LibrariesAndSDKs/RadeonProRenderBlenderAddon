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

from rprblender.utils import logging
log = logging.Log(tag='properties.object')


class RPR_ObjectProperites(RPR_Properties):
    """ Properties for objects. Should be available only for meshes and area lights """

    # Visibility
    visibility_in_primary_rays: BoolProperty(
        name="Camera",
        description="This object will be visible in camera rays",
        default=True,
    )
    reflection_visibility: BoolProperty(
        name="Reflections",
        description="This object will be visible in reflections",
        default=True,
    )
    refraction_visibility: BoolProperty(
        name="Refraction",
        description="This object will be visible in refractions",
        default=True,
    )
    diffuse_visibility: BoolProperty(
        name="Diffuse",
        description="This object will be visible in indirect diffuse reflections",
        default=True,
    )
    shadows: BoolProperty(
        name="Shadows",
        description="This object will cast shadows",
        default=True,
    )
    shadowcatcher: BoolProperty(
        name="Shadow Catcher",
        description="Use this object as a shadowcatcher",
        default=False,
    )
    portal_light: BoolProperty(
        name="Portal Light",
        description="Use this object as a portal light",
        default=False,
    )

    # Motion Blur
    motion_blur: BoolProperty(
        name="Motion Blur",
        description="Enable Motion Blur",
        default=True,
    )

    # Subdivision
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

    def export_visibility(self, rpr_shape):
        """ Exports visibility settings """

        rpr_shape.set_visibility_primary_only(self.visibility_in_primary_rays)
        rpr_shape.set_visibility_ex("visible.reflection", self.reflection_visibility)
        rpr_shape.set_visibility_ex("visible.reflection.glossy", self.reflection_visibility)
        rpr_shape.set_visibility_ex("visible.refraction", self.refraction_visibility)
        rpr_shape.set_visibility_ex("visible.refraction.glossy", self.refraction_visibility)
        rpr_shape.set_visibility_ex("visible.diffuse", self.diffuse_visibility)
        rpr_shape.set_shadow_catcher(self.shadowcatcher)
        rpr_shape.set_shadow(self.shadows)
        rpr_shape.set_visibility_ex("visible.shadow", self.shadows)

    def export_subdivision(self, rpr_shape):
        """ Exports subdivision settings """

        if self.subdivision:
            # convert factor from size of subdivision in pixel to RPR
            # RPR wants the subdivision factor as the "number of faces per pixel"
            # the setting gives user the size of face in number pixels.
            # rpr internally does: subdivision size in pixel = 2^factor  / 16.0
            factor = int(math.log2(1 / (16.0 * self.subdivision_factor)))

            rpr_shape.subdivision = {
                'factor': factor,
                'boundary': pyrpr.SUBDIV_BOUNDARY_INTERFOP_TYPE_EDGE_AND_CORNER if self.subdivision_boundary_type == 'EDGE_CORNER' else
                pyrpr.SUBDIV_BOUNDARY_INTERFOP_TYPE_EDGE_ONLY,
                'crease_weight': self.subdivision_crease_weight
            }

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
