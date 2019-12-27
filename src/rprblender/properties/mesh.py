import bpy
from bpy.props import (
    PointerProperty,
    IntProperty,
    StringProperty,
)

from . import RPR_Properties

from rprblender.utils import logging
log = logging.Log(tag='properties.mesh')


class RPR_MeshProperites(RPR_Properties):
    secondary_uv_layer_name: StringProperty(
        name="Secondary UV Map",
        description="Secondary UV Map",
        default="",
    )

    @property
    def primary_uv_layer(self):
        """ Get the mesh primary UV if present """
        uv_layers = self.id_data.uv_layers
        return next((uv for uv in uv_layers if uv.active_render), None)

    @property
    def primary_uv_name(self):
        layer = self.primary_uv_layer
        if layer:
            return layer.name
        return None

    @property
    def uv_sets_names(self):
        return tuple(uv.name for uv in self.id_data.uv_layers)

    def secondary_uv_layer(self, obj):
        """ Get the mesh secondary UV set if present """
        uv_layers = self.id_data.uv_layers
        # RPR field value can get lost if mesh has modifiers, use original object value
        if len(uv_layers) <= 1:
            return None

        secondary_name = obj.original.data.rpr.secondary_uv_layer_name
        if secondary_name:  # set is selected explicitly
            return next((uv for uv in uv_layers if uv.name == secondary_name), None)

        # if no secondary UV specified use the first non-primary set
        return next((uv for uv in uv_layers if not uv.active_render))

    @classmethod
    def register(cls):
        log("Register")
        bpy.types.Mesh.rpr = PointerProperty(
            name="RPR Mesh Settings",
            description="RPR Mesh settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Unregister")
        del bpy.types.Mesh.rpr
