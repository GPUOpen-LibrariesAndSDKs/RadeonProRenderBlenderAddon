import bpy

from rprblender.nodes import export
from rprblender.utils import logging
from . import RPR_Properties


log = logging.Log(tag='Material')


class RPR_MaterialParser(RPR_Properties):
    def sync(self, rpr_context):
        mat = self.id_data
        log("Syncing material: %s" % mat.name)

        exporter = export.MaterialExporter(rpr_context, mat)
        material = exporter.export()
        return material

    @classmethod
    def register(cls):
        log("Material: Register")
        bpy.types.Material.rpr = bpy.props.PointerProperty(
            name="RPR Material Settings",
            description="RPR material settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Material: Unregister")
        del bpy.types.Material.rpr

