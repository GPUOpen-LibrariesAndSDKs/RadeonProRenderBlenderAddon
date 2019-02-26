import bpy
from rprblender.engine.context import RPRContext
from rprblender.nodes import material_exporter
from . import key

from rprblender.utils import logging
log = logging.Log(tag='export.Material')


def sync(rpr_context: RPRContext, material: bpy.types.Material):
    """
    Creates pyrpr.MaterialNode or pyrprx.Material from bpy.types.Material.
    If material exists: returns existing material
    """

    log("sync", material)

    exporter = material_exporter.MaterialExporter(rpr_context, material)
    rpr_material = exporter.export()
    return rpr_material


def sync_update(rpr_context: RPRContext, material: bpy.types.Material):
    """ Recreates existing material """

    log("sync_update", material)

    mat_key = key(material)
    if mat_key in rpr_context.materials:
        rpr_context.remove_material(mat_key)

    sync(rpr_context, material)
    return True
