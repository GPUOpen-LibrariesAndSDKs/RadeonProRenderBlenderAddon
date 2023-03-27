#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
from dataclasses import dataclass
import numpy as np

import bpy

from . import particle, object, instance, material
from rprblender.utils import get_data_from_collection

from rprblender.utils import logging
log = logging.Log(tag='export.hair')


def key(p_sys, emitter, inst=None):
    if inst:
        return instance.key(inst) + particle.key(p_sys, emitter)

    return particle.key(p_sys, emitter)


@dataclass(init=False)
class CurveData:
    points: np.array
    uvs: np.array
    points_radii: np.array

    @staticmethod
    def init(p_sys: bpy.types.ParticleSystem, obj: bpy.types.Object, use_final_settings: bool):
        def shape_f(x, shape):
            """
            Adjust hair radius by Hair Shape
            f(0, shape) = 0, f(1, shape) = 1, f(x, 0) - linear
            shape > 0 - curved up, shape < 0 - curved down
            """
            return x ** (10.0 ** -shape)

        # render_steps is number of segments to render in power of 2
        settings = p_sys.settings

        render_step = settings.render_step if use_final_settings else settings.display_step
        length = 2 ** render_step + 1

        num_parents = len(p_sys.particles)
        start_index, curves_count = \
            (0, num_parents) if settings.child_type == 'NONE' else \
                (num_parents, len(p_sys.child_particles))

        # getting all points of all curves
        # Note: points which are not available are equal to (0, 0, 0).
        #       We will weld such points by updating (0, 0, 0) point to previous point
        all_points = np.fromiter(
            (elem for i in range(start_index, start_index + curves_count)
             for step in range(length)
             for elem in p_sys.co_hair(obj, particle_no=i, step=step)),
            dtype=np.float32
        ).reshape(-1, length, 3)

        # welding (0, 0, 0) point by previous point
        for curve in all_points:
            for i in range(1, length):
                # if all elements of curve[i] == 0 then make it equal to curve[i-1]
                if np.count_nonzero(curve[i]) == 0:
                    curve[i] = curve[i - 1]

        # getting indices of curves rows (points) with any non-zero values
        curve_indices = np.arange(len(all_points), dtype=np.int32)

        if len(curve_indices) == 0:
            return None

        data = CurveData()

        # calculating curve radii
        radius_scale = settings.radius_scale * sum(abs(x) for x in obj.matrix_world.to_scale()) / 3
        # Blender "radius" field value is in fact Diameter. Divide it by 2
        root = settings.root_radius * radius_scale / 2.
        tip = settings.tip_radius * radius_scale / 2.

        data.points_radii = np.fromiter(
            (root + (tip - root) * shape_f(i / (length - 1), settings.shape) for i in
             range(length)),
            dtype=np.float32)

        if settings.use_close_tip:
            data.points_radii[length - 1] = 0.0

        # getting final curve points
        data.points = np.ascontiguousarray(all_points[curve_indices], dtype=np.float32)

        if obj.type == 'MESH' and len(obj.data.uv_layers) > 0:
            # finding corresponded active ParticleSystemModifier
            p_modifier = next((modifier for modifier in obj.modifiers
                               if modifier.type == 'PARTICLE_SYSTEM' and
                               (modifier.show_render if use_final_settings
                                else modifier.show_viewport)
                               and modifier.particle_system.name == p_sys.name),
                              None)

            if not p_modifier:
                log.warn(f"No active particles modifier found for system {p_sys.name}")
                return None

            # getting all UVs
            all_uvs = np.fromiter(
                (elem for i in range(start_index, start_index + curves_count)
                 for elem in p_sys.uv_on_emitter(p_modifier,
                                                 particle=p_sys.particles[(i - start_index) % num_parents],
                                                 particle_no=i)),
                dtype=np.float32
            ).reshape(-1, 2)

            # getting final UVs
            data.uvs = np.ascontiguousarray(all_uvs[curve_indices], dtype=np.float32)

        else:
            data.uvs = None

        return data

    @staticmethod
    def init_curves(obj: bpy.types.Object):
        curves = obj.data

        data = CurveData()
        points_length = get_data_from_collection(curves.curves, 'points_length',
                                                 (len(curves.curves),), dtype=np.int32)
        points_length_max = np.max(points_length)
        points_length_min = np.min(points_length)
        if points_length_min == points_length_max:
            data.points = get_data_from_collection(curves.points, 'position',
                                                   (len(curves.curves), points_length_max, 3))

        else:
            points = get_data_from_collection(curves.points, 'position', (len(curves.points), 3))
            points_index = get_data_from_collection(curves.curves, 'first_point_index',
                                                    (len(curves.curves),), dtype=np.int32)
            data.points = np.zeros((len(curves.curves), points_length_max, 3), dtype=np.float32)
            for i in range(len(curves.curves)):
                for j in range(points_length_max):
                    data.points[i, j, :] = points[(points_index[i] + min(j, points_length[i] - 1)), :]

        # get radius for all control point
        points_radii = get_data_from_collection(curves.points, 'radius', (len(curves.curves), points_length_max))

        # check if radius the same for all control point,
        # in this case we generate radius for control points of one curve
        radius = points_radii[0][0]
        if np.all(points_radii == radius):
            radius = radius if radius != 0 else 0.005  # setting curve root radius same as in Cycles
            points_radii = np.full(points_length_max, radius, dtype=np.float32)

        data.points_radii = points_radii

        uv_data = None
        if 'surface_uv_coordinate' in curves.attributes.keys():
            uv_data = get_data_from_collection(
                curves.attributes['surface_uv_coordinate'].data, 'vector', (len(curves.curves), 2)
            )

        data.uvs = uv_data

        return data


def hair_p_sys(emitter):
    return (p_sys for p_sys in emitter.particle_systems if p_sys.settings.type == 'HAIR')


def sync(rpr_context, emitter: bpy.types.Object):
    """ sync the particle system """
    from rprblender.engine.render_engine import RenderEngine

    inst = None
    if isinstance(emitter, bpy.types.DepsgraphObjectInstance):
        inst = emitter
        emitter = emitter.object

    for p_sys in hair_p_sys(emitter):
        if p_sys.settings.render_type != 'PATH':
            log.warn("Skipping hair particle system type", p_sys.settings.render_type, p_sys, emitter)
            return

        log("sync", p_sys, emitter)

        curve_data = CurveData.init(p_sys, emitter, rpr_context.engine_type == RenderEngine.TYPE)
        if not curve_data:
            return

        if inst:
            hair_key = key(p_sys, emitter, inst)

            #  subtract emitter transforms from hair transform and apply instance/particle transform
            #  need because hair comes with emitter transform and applied twice
            transform = np.array(inst.matrix_world @ emitter.matrix_world.inverted(),
                                 dtype=np.float32)

        else:
            hair_key = key(p_sys, emitter)
            transform = np.identity(4, dtype=np.float32)

        rpr_hair = rpr_context.create_curve(hair_key, curve_data.points,
                                            curve_data.points_radii,
                                            curve_data.uvs)
        rpr_hair.set_name(str(hair_key))
        rpr_context.scene.attach(rpr_hair)

        rpr_material = particle.get_particle_system_material(rpr_context, p_sys, emitter)
        if rpr_material:
            rpr_hair.set_material(rpr_material)

        # hair uses world space
        rpr_hair.set_transform(transform)


def sync_update(rpr_context, emitter: bpy.types.Object, is_updated_geometry, is_updated_transform):
    updated = False
    obj_key = object.key(emitter)

    if rpr_context.has_curves(obj_key):
        rpr_context.remove_curves(obj_key)
        updated = True

    sync(rpr_context, emitter)

    if rpr_context.has_curves(obj_key):
        updated = True

    return updated


def sync_curves(rpr_context, obj: bpy.types.Object):
    log("sync_curves", obj, obj.data)

    try:
        curve_data = CurveData.init_curves(obj)
    except ValueError as e:
        log.error(e)
        return

    obj_key = object.key(obj)

    rpr_hair = rpr_context.create_curve_object(obj_key, curve_data.points, curve_data.points_radii, curve_data.uvs)
    rpr_hair.set_name(str(obj_key))
    rpr_context.scene.attach(rpr_hair)

    if obj.material_slots:
        slot = obj.material_slots[0]
        if slot.material:
            rpr_material = material.sync(rpr_context, slot.material, obj=obj)
            if rpr_material:
                rpr_hair.set_material(rpr_material)

    transform = object.get_transform(obj)
    rpr_hair.set_transform(transform)


def sync_update_curves(rpr_context, obj: bpy.types.Object, is_updated_geometry, is_updated_transform):
    log("sync_update_curves", obj, obj.data)

    obj_key = object.key(obj)
    rpr_hair = rpr_context.objects.get(obj_key, None)
    if not rpr_hair:
        sync_curves(rpr_context, obj)
        return obj_key in rpr_context.objects

    if is_updated_geometry:
        rpr_context.remove_object(obj_key)
        sync_curves(rpr_context, obj)
        return True

    if is_updated_transform:
        rpr_hair.set_transform(object.get_transform(obj))
        return True

    rpr_material = None
    if obj.material_slots:
        slot = obj.material_slots[0]
        if slot.material:
            rpr_material = material.sync(rpr_context, slot.material, obj=obj)

    rpr_hair.set_material(rpr_material)
    return True
