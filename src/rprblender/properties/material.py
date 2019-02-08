import bpy

from rprblender.nodes import export
from . import RPR_Properties
from rprblender.utils import key

from rprblender.utils import logging
log = logging.Log(tag='Material')


class RPR_MaterialParser(RPR_Properties):
    def sync(self, rpr_context):
        mat = self.id_data
        log("Syncing material", mat)

        exporter = export.MaterialExporter(rpr_context, mat)
        material = exporter.export()
        return material

    def sync_update(self, rpr_context):
        mat = self.id_data
        log("Updating material", mat)

        mat_key = key(mat)
        if mat_key in rpr_context.materials:
            rpr_context.remove_material(mat_key)

        self.sync(rpr_context)
        return True

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

