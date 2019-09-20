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
        uv_layers = self.id_data.uv_layers
        return next((uv for uv in uv_layers if uv.active_render), None)

    @property
    def secondary_uv_layer(self):
        uv_layers = self.id_data.uv_layers
        if len(uv_layers) <= 1 or not self.secondary_uv_layer_name:
            return None

        return next((uv for uv in uv_layers if uv.name == self.secondary_uv_layer_name), None)

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
