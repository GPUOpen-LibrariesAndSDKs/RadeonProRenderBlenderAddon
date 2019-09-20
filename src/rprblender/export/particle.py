from dataclasses import dataclass
import math
import numpy as np

import bpy
import mathutils

from . import mesh, material, object

from rprblender.utils import logging
log = logging.Log(tag='export.particle')


def key(p_sys: bpy.types.ParticleSystem, emitter: bpy.types.Object):
    return (object.key(emitter), p_sys.name)


def get_material_for_particles(rpr_context, p_sys, emitter):
    ''' Returns the material set for this particle system or None if none set or some other issue '''
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


def sync_particles(rpr_context, particle_system, master_shape, master_key):
    ''' Walk through particle list and create rpr_instances of ones that are ALIVE '''
    for i, particle in particle_system.particles.items():
        if not particle.alive_state == 'ALIVE':
            continue

        instance_key = (master_key, i)
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
            velocity = (particle.location[i] - particle.prev_location[i] for i in range(3))
            instance.set_linear_motion(*velocity)
            # TODO angular motion doesn't work right.
            #rotation = (particle.rotation[i] - particle.prev_rotation[i] for i in range(4))
            #instance.set_angular_motion(*rotation)


@dataclass(init=False)
class CurveData:
    points: np.array
    uvs: np.array
    radius: float

    @staticmethod
    def init(p_sys: bpy.types.ParticleSystem, obj: bpy.types.Object, is_preview: bool):
        # render_steps is number of segments to render in power of 2
        render_step = p_sys.settings.display_step if is_preview else p_sys.settings.render_step
        length = 2 ** render_step + 1

        num_parents = len(p_sys.particles)
        start_index, curves_count = \
            (0, num_parents) if p_sys.settings.child_type == 'NONE' else \
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
                # if module of curve[i] == 0 then make it equal to curve[i-1]
                if math.isclose(np.linalg.norm(curve[i]), 0.0):
                    curve[i] = curve[i-1]

        # getting indices of curves with length > 0
        curve_indices = np.fromiter(
            (i for i, curve in enumerate(all_points)
               if not math.isclose(np.linalg.norm(curve), 0.0)),
            dtype=np.int32
        )

        if len(curve_indices) == 0:
            return None

        data = CurveData()
        # getting final curve points
        data.points = np.ascontiguousarray(all_points[curve_indices], dtype=np.float32)

        if obj.type == 'MESH' and len(obj.data.uv_layers) > 0:
            # finding corresponded ParticleSystemModifier
            p_modifier = next(modifier for modifier in obj.modifiers
                                       if modifier.type == 'PARTICLE_SYSTEM' and
                                          modifier.particle_system.name == p_sys.name)

            # getting all UVs
            # TODO: p_sys.uv_on_emitter() working now only with 'particle' parameter,
            #       without it - crash on Blender's side
            all_uvs = np.fromiter(
                (elem for i in range(start_index, start_index + curves_count)
                      for elem in p_sys.uv_on_emitter(p_modifier,
                                  particle=p_sys.particles[(i - start_index) % num_parents])),
                dtype=np.float32
            ).reshape(-1, 2)

            # getting final UVs
            data.uvs = np.ascontiguousarray(all_uvs[curve_indices], dtype=np.float32)

        else:
            data.uvs = None

        data.radius = p_sys.settings.root_radius * p_sys.settings.radius_scale

        return data


def sync(rpr_context, p_sys: bpy.types.ParticleSystem, emitter: bpy.types.Object):
    """ sync the particle system """
    from rprblender.engine.preview_engine import PreviewEngine

    log("sync", p_sys, emitter)

    rpr_material = get_material_for_particles(rpr_context, p_sys, emitter)
    particle_key = key(p_sys, emitter)
    
    if p_sys.settings.type == 'HAIR':
        # hair does not have motion blur
        curve_data = CurveData.init(p_sys, emitter, rpr_context.engine_type == PreviewEngine.TYPE)
        if not curve_data:
            return
        
        rpr_hair = rpr_context.create_curve(particle_key, curve_data.points,
                                            curve_data.uvs, curve_data.radius)
        rpr_hair.set_name(str(particle_key))
        rpr_context.scene.attach(rpr_hair)

        if rpr_material:
            rpr_hair.set_material(rpr_material)

        # hair uses world space
        rpr_hair.set_transform(np.identity(4, dtype=np.float32))

    else:
        # this is an emitter
        # make master object for render type
        if p_sys.settings.render_type != 'HALO':
            log.warn("Skipping particle system type", p_sys.settings.render_type, p_sys, emitter)
            return

        master_shape = create_sphere_master(rpr_context, particle_key)

        # add master shape to scene but set to invisible.
        rpr_context.scene.attach(master_shape)
        master_shape.set_visibility(False)

        # add the material to master
        if rpr_material:
            master_shape.set_material(rpr_material)
            
        # export particles that are alive
        sync_particles(rpr_context, p_sys, master_shape, particle_key)
        


def sync_update(rpr_context, obj: bpy.types.Object, is_updated_geometry, is_updated_transform):
    # TODO.  Check for alive/undead particles.  If hair just change alltogether
    # Does this even need to be done at all?  Blender draws particles in OpenGL.
    pass