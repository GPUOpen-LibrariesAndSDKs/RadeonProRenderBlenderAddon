import bpy
import mathutils

from . import mesh, material, object
from rprblender.utils import logging
import numpy as np

log = logging.Log(tag='export.object')


def get_material_for_particles(rpr_context, particle_system, emitter):
    ''' Returns the material set for this particle system or None if none set or some other issue '''
    if len(emitter.material_slots):
        slot = emitter.material_slots[particle_system.settings.material-1] # don't know why these are indexed wrong?
        if slot.material:
            return material.sync(rpr_context, slot.material)
    return None

            
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


def extract_curve_data(p_sys, obj, is_preview=False):
    ''' Walk through hairs and get data, we need to put curves in segments of 4'''
    # render_steps is number of segments to render in power of 2
    render_step = p_sys.settings.display_step if is_preview else p_sys.settings.render_step
    length = 2 ** render_step + 1
    uvs = None

    # we must make segments of 4 pts for rpr
    # note that each segment must start with last point from before 
    # so for example the step indices for segments should be 0 1 2 3  3 4 5 6
    temp_steps = list(range(length))  
    steps = []
    while len(temp_steps):
        if len(temp_steps) < 4:
            # if < 4 left make a list of 4 repeating the last step
            steps.extend(temp_steps + [temp_steps[-1]] * (4-len(temp_steps)))
            break
        
        # add first 4 items to steps
        steps.extend(temp_steps[:4])
        # remove first 3 items, leave 4th to start next segment
        temp_steps = temp_steps[3:]

    length = len(steps)
    
    if p_sys.settings.child_type == 'NONE':
        num_curves = len(p_sys.particles)
        # make a iterator of 3D tuple, curve, step, elem
        
        points = np.fromiter((elem 
                                for i in range(num_curves)
                                for step in steps
                                for elem in p_sys.co_hair(obj, particle_no=i, step=step)),
                                dtype=np.float32).reshape((num_curves * length, 3))

        #if obj.type == 'MESH' and len(obj.data.tessface_uv_textures) > 0:
        #    uvs = np.fromiter((elem
        #                       for particle in p_sys.particles
        #                       for elem in p_sys.uv_on_emitter(p_modifier, particle, 0)),
        #                       dtype=np.float32).reshape((num_curves, 2))

    else:
        start_index = len(p_sys.particles)
        num_curves = len(p_sys.child_particles)
        points = np.fromiter((elem 
                                for i in range(start_index, num_curves + start_index)
                                for step in steps
                                for elem in p_sys.co_hair(obj, particle_no=i, step=step)),
                                dtype=np.float32).reshape((num_curves * length, 3))

        #if obj.type == 'MESH' and len(obj.data.tessface_uv_textures) > 0:
        #    uvs = np.fromiter((elem
        #                       for i in range(start_index, num_curves + start_index)
        #                       for elem in p_sys.uv_on_emitter(p_modifier, None, i)),
        #                       dtype=np.float32).reshape((num_curves, 2))

    radius = p_sys.settings.root_radius * p_sys.settings.radius_scale * 0.5

    return {
        'points' : points,
        'uvs': uvs,
        'radius': radius,
        'num_curves': num_curves,
        'curve_length': length
    }


def sync(rpr_context, particle_system: bpy.types.ParticleSystem, emitter):
    """ sync the particle system """

    log("Syncing particle system ", particle_system, " on emitter ", emitter)

    settings = particle_system.settings
    rpr_material = get_material_for_particles(rpr_context, particle_system, emitter)
    particle_key = (object.key(emitter), particle_system.name) # there can be the same particle system name on many objs
    
    if settings.type == 'HAIR':
        # hair does not have motion blur
        curve_data = extract_curve_data(particle_system, emitter, is_preview=rpr_context.is_preview)
        rpr_hair = rpr_context.create_curve(particle_key, curve_data['num_curves'], curve_data['curve_length'], 
                                            curve_data['points'], curve_data['uvs'], curve_data['radius'])
        rpr_context.scene.attach(rpr_hair)
        if rpr_material:
            rpr_hair.set_material(rpr_material)
        # hair uses world space
        rpr_hair.set_transform(np.identity(4, dtype=np.float32))
    else:
        # this is an emitter
        # make master object for render type
        if particle_system.settings.render_type != 'HALO':
            log("Skipping particle system type", particle_system.settings.render_type, particle_system)
            return

        master_shape = create_sphere_master(rpr_context, particle_key)

        # add master shape to scene but set to invisible.
        rpr_context.scene.attach(master_shape)
        master_shape.set_visibility(False)

        # add the material to master
        if rpr_material:
            master_shape.set_material(rpr_material)
            
        # export particles that are alive
        sync_particles(rpr_context, particle_system, master_shape, particle_key)
        


def sync_update(rpr_context, obj: bpy.types.Object, is_updated_geometry, is_updated_transform):
    # TODO.  Check for alive/undead particles.  If hair just change alltogether
    # Does this even need to be done at all?  Blender draws particles in OpenGL.
    pass