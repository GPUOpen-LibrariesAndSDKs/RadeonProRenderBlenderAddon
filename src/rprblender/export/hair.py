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

from . import particle, object

from rprblender.utils import logging
log = logging.Log(tag='export.hair')


def key(p_sys, emitter):
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
                               modifier.show_render and
                               modifier.particle_system.name == p_sys.name),
                              None)

            if not p_modifier:
                log.warn(f"No active particles modifier found for system {p_sys.name}")
                return None

            # getting all UVs
            all_uvs = np.fromiter(
                (elem for i in range(start_index, start_index + curves_count)
                 for elem in p_sys.uv_on_emitter(p_modifier,
                                                 particle=p_sys.particles[
                                                     (i - start_index) % num_parents])),
                dtype=np.float32
            ).reshape(-1, 2)

            # getting final UVs
            data.uvs = np.ascontiguousarray(all_uvs[curve_indices], dtype=np.float32)

        else:
            data.uvs = None

        return data


def hair_p_sys(emitter):
    return (p_sys for p_sys in emitter.particle_systems if p_sys.settings.type == 'HAIR')


def sync(rpr_context, emitter: bpy.types.Object):
    """ sync the particle system """
    from rprblender.engine.render_engine import RenderEngine

    for p_sys in hair_p_sys(emitter):
        log("sync", p_sys, emitter)

        curve_data = CurveData.init(p_sys, emitter, rpr_context.engine_type == RenderEngine.TYPE)
        if not curve_data:
            return

        hair_key = key(p_sys, emitter)
        rpr_hair = rpr_context.create_curve(hair_key, curve_data.points,
                                            curve_data.points_radii,
                                            curve_data.uvs)
        rpr_hair.set_name(str(hair_key))
        rpr_context.scene.attach(rpr_hair)

        rpr_material = particle.get_particle_system_material(rpr_context, p_sys, emitter)
        if rpr_material:
            rpr_hair.set_material(rpr_material)

        # hair uses world space
        rpr_hair.set_transform(np.identity(4, dtype=np.float32))


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
