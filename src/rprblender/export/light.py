import numpy as np
import math

import bmesh
import mathutils
import bpy

from rprblender.engine.context import RPRContext
from . import key, get_transform
from rprblender.properties import SyncError
from rprblender.properties.light import MAX_LUMINOUS_EFFICACY
from . import mesh, image
from rprblender.utils.conversion import convert_kelvins_to_rgb

from rprblender.utils import logging
log = logging.Log(tag='export.light')


def get_radiant_power(light: bpy.types.Light, area=0.0):
    """ Return light radiant power depending of light type and selected units """

    rpr = light.rpr

    # calculating color intensity
    color = np.array(light.color)
    if rpr.use_temperature:
        color *= convert_kelvins_to_rgb(rpr.temperature)
    intensity = color * rpr.intensity

    # calculating radian power for core
    if light.type in ('POINT', 'SPOT'):
        units = rpr.intensity_units_point
        if units == 'DEFAULT':
            return intensity / (4*math.pi)  # dividing by 4*pi to be more convenient with cycles point light

        # converting to lumen
        if units == 'LUMEN':
            lumen = intensity
        elif units == 'WATTS':
            lumen = intensity * rpr.luminous_efficacy
        else:
            raise ValueError("Incorrect light units value", light, units)

        return lumen / MAX_LUMINOUS_EFFICACY

    elif light.type == 'SUN':
        units = rpr.intensity_units_dir
        if units == 'DEFAULT':
            return intensity * 0.01         # multiplying by 0.01 to be more convenient with point light

        # converting to luminance
        if units == 'LUMINANCE':
            luminance = intensity
        elif units == 'RADIANCE':
            luminance = intensity * rpr.luminous_efficacy
        else:
            raise ValueError("Incorrect light units value", light, units)

        return luminance / MAX_LUMINOUS_EFFICACY

    elif light.type == 'AREA':
        units = rpr.intensity_units_area
        if units == 'DEFAULT':
            if rpr.intensity_normalization:
                return intensity / area
            return intensity

        # converting to luminance
        if units == 'LUMEN':
            luminance = intensity / area
        elif units == 'WATTS':
            luminance = intensity * rpr.luminous_efficacy / area
        elif units == 'LUMINANCE':
            luminance = intensity
        elif units == 'RADIANCE':
            luminance = intensity * rpr.luminous_efficacy
        else:
            raise ValueError("Incorrect light units value", light, units)

        return luminance / MAX_LUMINOUS_EFFICACY


def sync(rpr_context: RPRContext, obj: bpy.types.Object):
    """ Creates pyrpr.Light from obj.data: bpy.types.Light """

    light = obj.data
    rpr = light.rpr
    log("sync", light, obj)

    area = 0.0
    light_key = key(obj)

    if light.type == 'POINT':
        if light.rpr.ies_file_name:
            rpr_light = rpr_context.create_light(light_key, 'ies')
            rpr_light.set_image_from_file(light.rpr.ies_file_name, 256, 256)
        else:
            rpr_light = rpr_context.create_light(light_key, 'point')

    elif light.type in ('SUN', 'HEMI'):  # just in case old scenes will have outdated Hemi
        rpr_light = rpr_context.create_light(light_key, 'directional')
        rpr_light.set_shadow_softness(light.rpr.shadow_softness)

    elif light.type == 'SPOT':
        rpr_light = rpr_context.create_light(light_key, 'spot')
        oangle = 0.5 * light.spot_size  # half of spot_size
        iangle = oangle * (1.0 - light.spot_blend * light.spot_blend)  # square dependency of spot_blend
        rpr_light.set_cone_shape(iangle, oangle)

    elif light.type == 'AREA':
        if rpr.shape == 'MESH':
            if not rpr.mesh:
                raise SyncError("Area light %s has no mesh" % light.name, light)

            data = mesh.MeshData.init_from_mesh(rpr.mesh, calc_area=True)

        else:
            data = mesh.MeshData.init_from_shape_type(rpr.shape, light.size, light.size_y, segments=32)

        area = data.area

        rpr_light = rpr_context.create_area_light(
            light_key,
            data.vertices, data.normals, data.uvs,
            data.vertex_indices, data.normal_indices, data.uv_indices,
            data.num_face_vertices
        )

        rpr_light.set_visibility(rpr.visible)
        rpr_light.set_shadow(rpr.visible and rpr.cast_shadows)

        if rpr.color_map:
            rpr_light.set_image(image.sync(rpr_context, rpr.color_map))

    else:
        raise SyncError("Light %s has unsupported type %s" % (light.name, light.type), light)

    rpr_light.set_name(light.name)

    power = get_radiant_power(light, area)
    rpr_light.set_radiant_power(*power)
    rpr_light.set_transform(get_transform(obj))
    rpr_light.set_group_id(1 if light.rpr.group == 'KEY' else 2)

    rpr_context.scene.attach(rpr_light)


def sync_update(rpr_context: RPRContext, obj: bpy.types.Object, is_updated_geometry, is_updated_transform):
    """ Update existing light from obj.data: bpy.types.Light or create a new light """

    light = obj.data
    log("sync_update", light, obj, is_updated_geometry, is_updated_transform)

    res = False

    rpr_light = rpr_context.objects.get(key(obj), None)
    if rpr_light:
        if is_updated_geometry:
            # TODO: recreate light
            pass

        if is_updated_transform:
            rpr_light.set_transform(get_transform(obj))
            res = True

    else:
        sync(rpr_context, obj)
        res = True

    return res


