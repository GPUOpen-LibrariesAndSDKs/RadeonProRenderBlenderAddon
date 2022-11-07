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
import numpy as np

import bpy
import mathutils

from . import mesh, material, object

from rprblender.utils import logging
log = logging.Log(tag='export.particle')


def key(p_sys: bpy.types.ParticleSystem, emitter: bpy.types.Object):
    return (object.key(emitter), p_sys.name)


def get_particle_system_material(rpr_context, p_sys, emitter):
    """Returns the material set for this particle system or None if none set or some other issue"""

    if len(emitter.material_slots) == 0:
        return None

    if (p_sys.settings.material - 1) < len(emitter.material_slots):
        slot = emitter.material_slots[p_sys.settings.material - 1]
    else:
        slot = emitter.material_slots[-1]

    if not slot.material:
        return None

    return material.sync(rpr_context, slot.material, obj=emitter)

            
def create_sphere_master(rpr_context, master_key):
    ''' create a sphere rpr shape to be used as instance master '''
    data = mesh.MeshData.init_from_shape_type('SPHERE', 1.0, 1.0, segments=32)
    return rpr_context.create_mesh(
        master_key, data.vertices, data.normals, data.uvs,
        data.vertex_indices, data.normal_indices, data.uv_indices,
        data.num_face_vertices
    )


def emitter_p_sys(emitter):
    return (p_sys for p_sys in emitter.particle_systems if p_sys.settings.type == 'EMITTER')


def sync(rpr_context, emitter: bpy.types.Object):
    """ sync the particle system """

    for p_sys in emitter_p_sys(emitter):
        if p_sys.settings.render_type != 'HALO':
            log.warn("Skipping particle system type", p_sys.settings.render_type, p_sys, emitter)
            return

        log("sync", p_sys, emitter)

        particle_key = key(p_sys, emitter)

        # make master object for render type
        master_shape = create_sphere_master(rpr_context, particle_key)

        # add master shape to scene but set to invisible.
        rpr_context.scene.attach(master_shape)
        master_shape.set_visibility(False)

        # add the material to master
        rpr_material = get_particle_system_material(rpr_context, p_sys, emitter)
        if rpr_material:
            master_shape.set_material(rpr_material)

        # walk through particle list and create rpr_instances of ones that are ALIVE
        for i, particle in p_sys.particles.items():
            if not particle.alive_state == 'ALIVE':
                continue

            instance_key = (particle_key, i)
            instance = rpr_context.create_instance(instance_key, master_shape)

            loc = mathutils.Matrix.Translation(particle.location)
            scale = mathutils.Matrix.Scale(particle.size, 4)
            rot = mathutils.Quaternion(particle.rotation)
            mat = np.array(loc @ rot.to_matrix().to_4x4() @ scale, dtype=np.float32).reshape(4, 4)

            rpr_context.scene.attach(instance)
            instance.set_transform(mat)
            instance.set_visibility(True)

            # do motion blur.
            if rpr_context.do_motion_blur:
                prev_loc = mathutils.Matrix.Translation(particle.prev_location)
                prev_mat = np.array(prev_loc @ rot.to_matrix().to_4x4() @ scale,
                                    dtype=np.float32).reshape(4, 4)
                instance.set_motion_transform(prev_mat)


def sync_update(rpr_context, emitter: bpy.types.Object,
                is_updated_geometry, is_updated_transform):
    # TODO: Implement sync_update
    return False
