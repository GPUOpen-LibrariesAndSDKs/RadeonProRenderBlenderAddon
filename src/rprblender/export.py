import cProfile
import time
import traceback
import math
import weakref
import ctypes

import bpy
import bmesh
import numpy as np
import mathutils
from mathutils import Matrix, Euler, Quaternion
import itertools

import pyrpr
from pyrpr import ffi

from rprblender import helpers, versions
from rprblender.timing import TimedContext
from rprblender import config
from . import logging
from rprblender.helpers import CallLogger

call_logger = CallLogger(tag='export')


class ObjectKey:
    """This is for easier debugging - stores original object string representation
    along with simple integer hash value that is used as key hash"""

    def __init__(self, value):
        self.value = value.as_pointer()
        self.hash = hash(self.value)
        if config.debug:
            self.str_repr = '<id: %s, %s> ' % (self.value, self.hash) + str(value)
        else:
            self.str_repr = str(self.value)

    def __hash__(self):
        return self.hash

    def __eq__(self, other):
        return self.value == other.value

    def __ne__(self, other):
        return self.value != other.value

    def __str__(self):
        return self.str_repr

    def __repr__(self):
        return self.str_repr


class InstanceKey:
    """This is for easier debugging - stores original object string representation
    along with simple integer hash value that is used as key hash"""

    def __init__(self, duplicator, dupli):
        persistent_id = tuple(dupli.persistent_id)
        self.value = (duplicator.as_pointer(), persistent_id)
        self.hash = hash(self.value)
        if config.debug:
            self.str_repr = '<object: %s, duplicator: %s, id: %s, hash: %s> ' % (
                dupli.object,
                duplicator,
                (hex(self.value[0]), ', '.join(hex(v) for v in self.value[1])),
                self.hash)

        else:
            self.str_repr = str(self.value)

    def __hash__(self):
        return self.hash

    def __eq__(self, other):
        return self.value == other.value

    def __ne__(self, other):
        return self.value != other.value

    def __str__(self):
        return self.str_repr

    def __repr__(self):
        return self.str_repr


def get_object_key(obj):
    if obj is None: return None
    if config.debug:
        assert isinstance(obj, bpy.types.bpy_struct), obj
        return ObjectKey(obj)
    return obj.as_pointer()


def get_instance_key(duplicator, dupli):
    # different duplis can be instances of the same object and persistent_id differentiates them
    if config.debug:
        return InstanceKey(duplicator, dupli)
    return duplicator.as_pointer(), tuple(dupli.persistent_id)


def get_materials(obj):
    materials = []

    if hasattr(obj, 'material_slots'):
        for matSlot in obj.material_slots:
            materials.append(matSlot.material)

    # fixme:
    # if hasattr(obj.data, 'materials'):
    #    for mat in obj.data.materials:
    #        materials.append(mat)

    return materials


class EnvironmentExportState:
    ibl = None
    background_override = None
    ibl_background_override_proxy_name = None
    scene_synced = None

    sun_sky = None
    sun_sky_image_buffer = None

    SKY_TEXTURE_BITS_COUNT = 3

    def get_sun_sky_size(self, texture_resolution):
        if texture_resolution == 'high':
            return 4096
        elif texture_resolution == 'small':
            return 256

        return 1024

    sun_sky_size = None

    def sun_sky_create_buffer(self, texture_resolution):
        size = self.get_sun_sky_size(texture_resolution)
        if self.sun_sky_size != size or not self.sun_sky_image_buffer:
            self.sun_sky_image_buffer = np.ones((size, size, self.SKY_TEXTURE_BITS_COUNT), dtype=np.float32)
            self.sun_sky_size = size

    def sun_sky_destroy_buffer(self):
        self.sun_sky_image_buffer = None

    def sun_sky_detach(self):
        if self.sun_sky and self.sun_sky.attached:
            self.sun_sky.detach()

    def ibl_detach(self):
        if self.ibl and self.ibl.attached:
            self.ibl.detach()

    def background_disable(self):
        self.scene_synced.background_set(None)


class ObjectMesh:
    def __init__(self, blender_obj, extracted_mesh):
        self.blender_obj = blender_obj
        self.data = extracted_mesh
        self.material_indices_used = np.unique(self.data['data']['faces_materials']) if self.data else []

    def get_materials(self):
        return get_materials(self.blender_obj)

    def enumerate_used_materials(self):
        for i, m in enumerate(get_materials(self.blender_obj)):
            if i in self.material_indices_used:
                yield i, m

    def get_prototype_key(self):
        return get_object_key(self.blender_obj)


class MeshSync:
    def __init__(self, object_mesh: ObjectMesh):
        self.object_mesh = object_mesh
        self.materials_assigned = {}
        self.matrix = None

    @property
    def material_indices_used(self):
        return self.object_mesh.material_indices_used

    def get_materials(self):
        return self.object_mesh.get_materials()

    def enumerate_used_materials(self):
        yield from self.object_mesh.enumerate_used_materials()

    def get_prototype_key(self):
        return self.object_mesh.get_prototype_key()

    def set_matrix(self, matrix):
        self.matrix = np.array(matrix, dtype=np.float32)


class InstanceSync(MeshSync): pass


def log_sync(*message):
    logging.debug(*message, tag='export.sync')


def log_export(*message):
    logging.debug(*message, tag='export')


class ObjectsSync:
    def __init__(self, scene_export: 'SceneExport'):
        self.scene_export = scene_export
        self.scene_synced = scene_export.scene_synced

        self.object_instances_instantiated_as_mesh_prototype = set()
        self.object_instances_instantiated_as_mesh_instance = set()

        self.object_instances = {}

        self.prototypes = {}
        self.instances = {}
        self.instances_for_duplicator = {}
        self.instances_for_prototype = {}
        self.duplicator_for_instance = {}
        self.duplicator_for_prototype = {}

        self.mesh_added_for_prototype = {}
        self.instances_added_for_prototype = {}

        self.materials_added = {}
        self.material_for_submesh = {}

    def init_materials(self):
        objects_needing_material_update = {}

        for key in self.object_instances_instantiated_as_mesh_prototype:
            sync = self.object_instances[key]
            for material_index, material in sync.enumerate_used_materials():
                if material:
                    if material not in objects_needing_material_update:
                        objects_needing_material_update[material] = set()
                    objects_needing_material_update[material].add((key, material_index))

        for material, keys in objects_needing_material_update.items():
            self.update_material(keys, material)

        submesh_instances_needing_material_update = {}

        for key, sync in self.instances.items():
            for material_index, material in sync.enumerate_used_materials():
                if material:
                    if material not in submesh_instances_needing_material_update:
                        submesh_instances_needing_material_update[material] = set()
                    if key != self.mesh_added_for_prototype.get(sync.get_prototype_key(), None):
                        submesh_instances_needing_material_update[material].add((key, material_index))

        for material, submesh_instances in submesh_instances_needing_material_update.items():
            mat_key = get_object_key(material)
            if mat_key not in self.materials_added:
                self.add_material(material, mat_key)
            for instance_key, material_index in submesh_instances:
                self.scene_synced.assign_material_to_mesh_instance(mat_key, (instance_key, material_index))

    def update_material(self, sumbesh_keys, blender_mat):
        log_sync('update_material', sumbesh_keys, blender_mat)

        key = get_object_key(blender_mat) if blender_mat else None

        for submesh_key in sumbesh_keys:
            if submesh_key in self.material_for_submesh:
                self.scene_synced.remove_material_from_mesh(submesh_key,key)
                for instance_key in self.get_instances_added_for_prototype(submesh_key[0]):
                    self.scene_synced.remove_material_from_mesh_instance((instance_key, submesh_key[1]))

        if key is not None:
            if key in self.materials_added:
                self.scene_synced.remove_material(key)
                del self.materials_added[key]
            self.add_material(blender_mat, key)
            for submesh_key in sumbesh_keys:
                prototype_key, material_index = submesh_key
                if self.is_object_instantiated_as_mesh_prototype(prototype_key):
                    self.material_for_submesh[submesh_key] = key
                    self.scene_synced.assign_material_to_mesh(key, submesh_key)
                    for instance_key in self.get_instances_added_for_prototype(prototype_key):
                        self.scene_synced.assign_material_to_mesh_instance(key, (instance_key, material_index))

    def update_instance_materials(self, instance_key):
        if instance_key not in self.instances:
            return
        sync = self.instances[instance_key]

        for material_index, material in sync.enumerate_used_materials():
            if material:
                mat_key = get_object_key(material)
                if mat_key not in self.materials_added:
                    self.add_material(material, mat_key)
                if self.is_object_instantiated_as_mesh_prototype(instance_key):
                    self.scene_synced.assign_material_to_mesh(mat_key, (instance_key, material_index))
                else:
                    self.scene_synced.assign_material_to_mesh_instance(mat_key, (instance_key, material_index))

    @call_logger.logged
    def add_material(self, blender_mat, key):
        self.scene_synced.add_material(key, blender_mat)
        self.materials_added[key] = True

    @call_logger.logged
    def is_object_instantiated_as_mesh_prototype(self, key):
        return key in self.object_instances_instantiated_as_mesh_prototype

    @call_logger.logged
    def is_object_instantiated_as_mesh_instance(self, key):
        return key in self.object_instances_instantiated_as_mesh_instance

    @call_logger.logged
    def instantiate_object_instance_as_mesh(self, key, sync):
        prototype_key = sync.get_prototype_key()
        matrix = sync.matrix

        if prototype_key in self.mesh_added_for_prototype:
            self.instantiate_object_instance_as_mesh_instance(
                key, self.mesh_added_for_prototype[prototype_key], matrix)
        else:
            self.instantiate_object_instance_as_mesh_prototype(key, sync)

    @call_logger.logged
    def deinstantiate_object_instance_as_mesh(self, key):
        if self.is_object_instantiated_as_mesh_prototype(key):
            self.deinstantiate_object_instance_as_mesh_prototype(key)
        elif self.is_object_instantiated_as_mesh_instance(key):
            self.deinstantiate_object_instance_as_mesh_instance(key)

    @call_logger.logged
    def instantiate_object_instance_as_mesh_instance(self, key, mesh_key, matrix):
        mesh_sync = self.object_instances[mesh_key]
        sync = self.object_instances[key]
        prototype_key = sync.get_prototype_key()

        self.instances_added_for_prototype[prototype_key].add(key)
        self.object_instances_instantiated_as_mesh_instance.add(key)

        for i in mesh_sync.materials_assigned:
            sync.materials_assigned[i] = True
            self.scene_synced.add_mesh_instance((key, i), ((mesh_key, i), matrix))

        for material_index in mesh_sync.materials_assigned:
            prototype_submesh_key = prototype_key, material_index
            if prototype_submesh_key in self.material_for_submesh:
                mat_key = self.material_for_submesh[prototype_submesh_key]
                self.scene_synced.assign_material_to_mesh_instance(mat_key, (key, material_index))

    @call_logger.logged
    def deinstantiate_object_instance_as_mesh_instance(self, key):
        sync = self.object_instances[key]

        for i in sync.materials_assigned:
            self.scene_synced.remove_material_from_mesh_instance((key, i))
            self.scene_synced.remove_mesh_instance((key, i))

        self.instances_added_for_prototype[sync.get_prototype_key()].remove(key)
        self.object_instances_instantiated_as_mesh_instance.remove(key)

    @call_logger.logged
    def instantiate_object_instance_as_mesh_prototype(self, key, sync):
        """  Add instance of blender object, assign specified key to the instance """

        # TODO: scale also needs to sync, better remove this dependency from geometry
        # extraction and move it to matrix
        # TODO: cache extracted submesh

        log_sync('material_indices_used:', sync.material_indices_used)
        for i in sync.material_indices_used:
            self.scene_synced.add_mesh((key, i), extract_submesh(sync.object_mesh.data, i, 1), sync.matrix)
            sync.materials_assigned[i] = True
        self.object_instances_instantiated_as_mesh_prototype.add(key)
        self.mesh_added_for_prototype[sync.get_prototype_key()] = key

        self.update_settings(key, sync.object_mesh.blender_obj.rpr_object)

    @call_logger.logged
    def deinstantiate_object_instance_as_mesh_prototype(self, key):
        mesh_sync = self.object_instances[key]
        prototype_key = self.object_instances[key].get_prototype_key()

        for i in mesh_sync.materials_assigned:
            mat_key = 0
            prototype_submesh_key = prototype_key, i
            if prototype_submesh_key in self.material_for_submesh:
                mat_key = self.material_for_submesh[prototype_submesh_key]
            self.scene_synced.remove_material_from_mesh((key, i), mat_key)
            self.scene_synced.remove_mesh((key, i))

        del self.mesh_added_for_prototype[prototype_key]
        self.object_instances_instantiated_as_mesh_prototype.remove(key)

        # TODO: something more intelligent for object cache cleanup!
        self.remove_prototype(prototype_key)
        self.scene_export.remove_mesh_data_from_cache(key)

    @call_logger.logged
    def add_object_instance(self, key, obj_key, obj, matrix_world):
        sync = self.create_object_instance_sync(key, obj_key, obj, matrix_world)
        if not sync:
            return
        return sync

    @call_logger.logged
    def remove_object_instance(self, key):
        if key not in self.object_instances:
            return

        # TODO: remove all instances of the object
        # TODO: support instances removal from scene_synced

        log_sync('self.prototypes:', self.prototypes)
        self.deinstantiate_object_instance_as_mesh(key)

        del self.object_instances[key]

    def get_instances_for_duplicator(self, duplicator_key):
        return self.instances_for_duplicator[duplicator_key]

    def get_instances_added_for_prototype(self, prototype_key):
        return self.instances_added_for_prototype.get(prototype_key, [])

    @call_logger.logged
    def add_instance(self, duplicator_key, key, dupli):
        log_sync('dupli:', dupli.object, dupli.object.type, dupli.object.library, dupli.matrix)

        sync = self.add_object_instance(key, get_object_key(dupli.object), dupli.object, dupli.matrix)
        if not sync:
            return

        self.instances_for_duplicator.setdefault(duplicator_key, set()).add(key)
        self.instances_for_prototype.setdefault(sync.get_prototype_key(), set()).add(key)
        self.duplicator_for_instance[key] = duplicator_key
        self.instances[key] = sync

        if sync.get_prototype_key() not in self.duplicator_for_prototype:
            self.duplicator_for_prototype[sync.get_prototype_key()] = set()
        self.duplicator_for_prototype[sync.get_prototype_key()].add(duplicator_key)

        self.instantiate_object_instance_as_mesh(key, sync)

    @call_logger.logged
    def remove_instance(self, key):

        instance = self.object_instances[key]

        prototype_key = instance.get_prototype_key()

        del self.instances[key]
        duplicator_key = self.duplicator_for_instance.pop(key)
        self.instances_for_prototype[prototype_key].remove(key)
        self.instances_for_duplicator[duplicator_key].remove(key)

        self.remove_object_instance(key)

    def create_object_instance_sync(self, key, prototype_key, prototype, matrix):
        prototype = self.get_prototype(prototype_key, prototype)
        if not prototype:
            return

        mesh_sync = MeshSync(prototype)
        self.object_instances[key] = mesh_sync

        mat = matrix.copy()
        mat[0][3] = mat[0][3]
        mat[1][3] = mat[1][3]
        mat[2][3] = mat[2][3]
        mesh_sync.set_matrix(mat)
        return mesh_sync

    def get_prototype(self, prototype_key, obj):
        try:
            return self.prototypes[prototype_key]
        except KeyError:
            prototype = self.add_prototype(obj)
            if prototype is not None:
                self.prototypes[prototype_key] = prototype
                self.instances_added_for_prototype[prototype_key] = set()
            return prototype

    @call_logger.logged
    def add_prototype(self, obj):
        extracted_mesh = self.scene_export.to_mesh(obj)
        # mesh might not be added because it has not polygons
        mesh = None
        if extracted_mesh:
            mesh = ObjectMesh(obj, extracted_mesh)
        return mesh

    def remove_prototype(self, prototype_key):
        assert not self.instances_added_for_prototype[prototype_key]
        del self.instances_added_for_prototype[prototype_key]
        del self.prototypes[prototype_key]

    def is_duplicator(self, obj_key):
        return obj_key in self.instances_for_duplicator

    def remove_duplicator_instances(self, duplicator_key):
        for instance in list(self.get_instances_for_duplicator(duplicator_key)):
            self.remove_instance(instance)
        del self.instances_for_duplicator[duplicator_key]

        for duplicators in self.duplicator_for_prototype.values():
            duplicators.remove(duplicator_key)

    def sync_duplicator_instances(self, obj_key, obj):
        for key, dupli in self.scene_export.iter_dupli_from_duplicator(obj):
            # if key in self.object_instances:
            #     self.deinstantiate_object_instance_as_mesh(key)
            pass

        for key, dupli in self.scene_export.iter_dupli_from_duplicator(obj):
            if key in self.object_instances:
                # self.instantiate_object_instance_as_mesh(key, self.object_instances[key])
                self.update_object_instance_transform(
                    key, self.object_instances[key].get_prototype_key(), dupli.matrix)
            else:
                self.add_instance(obj_key, key, dupli)

    def update_object_data(self, obj_key, obj):
        if obj_key not in self.object_instances:
            sync = self.add_object_instance(obj_key, obj_key, obj, obj.matrix_world)
            if sync:
                self.instantiate_object_instance_as_mesh(obj_key, sync)
            return

        instances_to_readd = []

        sync = self.object_instances[obj_key]
        prototype_key = sync.get_prototype_key()

        for instance_key in list(self.instances_added_for_prototype.get(prototype_key, [])):
            assert instance_key in self.object_instances
            instance_sync = self.object_instances[instance_key]
            instances_to_readd.append((instance_key, instance_sync))
            self.deinstantiate_object_instance_as_mesh(instance_key)

        self.remove_object_instance(obj_key)

        # cleanup mesh cache
        # self.remove_prototype(obj_key)
        # self.scene_export.remove_mesh_data_from_cache(obj_key)

        sync = self.add_object_instance(obj_key, obj_key, obj, obj.matrix_world)
        if sync:
            self.instantiate_object_instance_as_mesh(obj_key, sync)

        for instance_key, instance_sync in instances_to_readd:
            instance_sync.object_mesh = sync.object_mesh
            self.object_instances[instance_key] = instance_sync
            self.instantiate_object_instance_as_mesh(instance_key, instance_sync)

    def remove_instances_for_prototype(self, obj_key):
        log_sync('instances_for_prototype:', self.instances_for_prototype)
        if obj_key in self.instances_for_prototype:
            for instance_key in list(self.instances_for_prototype[obj_key]):
                self.remove_instance(instance_key)

    def show_object(self, key):
        if not self.is_object_instantiated_as_mesh_prototype(key):
            return
        mesh_sync = self.object_instances[key]
        for i in mesh_sync.materials_assigned:
            self.scene_synced.show_mesh((key, i))

    def hide_object(self, key):
        mesh_sync = self.object_instances[key]
        for i in mesh_sync.materials_assigned:
            self.scene_synced.hide_mesh((key, i))

    @call_logger.logged
    def update_object_transform(self, key, obj):
        # TODO: support instances
        if not self.is_object_instantiated_as_mesh_prototype(key):
            return

        mesh_sync = self.object_instances[key]
        for i in mesh_sync.materials_assigned:
            self.scene_synced.update_mesh_transform((key, i), obj.matrix_world)

    @call_logger.logged
    def update_instance_transform(self, key, obj_key, matrix):
        mesh_sync = self.object_instances[key]
        for i in mesh_sync.materials_assigned:
            self.scene_synced.update_instance_transform((key, i), matrix)

    @call_logger.logged
    def update_object_instance_transform(self, key, obj_key, matrix):
        if self.is_object_instantiated_as_mesh_prototype(key):
            sync = self.object_instances[key]
            sync.set_matrix(matrix)
            for i in sync.materials_assigned:
                self.scene_synced.update_mesh_transform((key, i), matrix)
        elif self.is_object_instantiated_as_mesh_instance(key):
            sync = self.object_instances[key]
            sync.set_matrix(matrix)
            self.update_instance_transform(key, obj_key, matrix)

    def update_settings(self, key, object_settings):
        if key not in self.object_instances:
            return
        mesh_sync = self.object_instances[key]
        motion_blur = self.scene_export.get_object_motion_blur(mesh_sync)

        for i in mesh_sync.materials_assigned:
            self.scene_synced.mesh_set_shadowcatcher((key, i), object_settings.shadowcatcher)
            self.scene_synced.mesh_set_shadows((key, i), object_settings.shadows)
            self.scene_synced.mesh_set_subdivision(
                (key, i), object_settings.subdivision,
                helpers.subdivision_boundary_prop.remap[object_settings.subdivision_boundary],
                object_settings.subdivision_crease_weight,
            )

            #self.scene_synced.mesh_set_visibility((key, i), object_settings.visibility)
            self.scene_synced.mesh_set_visibility_in_primary_rays((key, i), object_settings.visibility_in_primary_rays)
            #self.scene_synced.mesh_set_visibility_in_specular((key, i), object_settings.visibility_in_specular)

            if object_settings.portallight:
                self.scene_synced.mesh_attach_portallight((key, i))
            else:
                self.scene_synced.mesh_detach_portallight((key, i))

            if motion_blur is not None:
                self.scene_synced.set_motion_blur((key, i), *motion_blur)
            else:
                self.scene_synced.reset_motion_blur((key, i))


class ObjectsSyncFrame:
    def __init__(self, scene_export: 'SceneExport', objects_sync: 'ObjectsSync'):
        self.scene_export = scene_export
        self.objects_sync = objects_sync
        self.duplicators_added = []
        self.duplicators_updated = set()
        self.meshes_updated_data = {}
        self.objects_needing_material_update = {}

        self.materials_updated = None

    def create_materials_updated_list(self):
        self.materials_updated = {get_object_key(mat)
                                  for mat in self.objects_needing_material_update if mat}
        log_sync("materials_updated:", self.materials_updated)

    def was_material_updated(self, mat_key):
        return mat_key in self.materials_updated

    def add_duplicator(self, obj):
        self.duplicators_added.append(obj)

    def add_instances_for_prototype(self, obj_key):
        if obj_key in self.objects_sync.instances_for_prototype:
            for duplicator_key in self.objects_sync.duplicator_for_prototype[obj_key]:
                self.duplicators_updated.add(duplicator_key)

    def update_object_data(self, obj_key, obj):
        self.meshes_updated_data[obj_key] = obj

    def update_object_transform(self, obj_key, obj):
        if obj_key not in self.objects_sync.object_instances:
            sync = self.objects_sync.add_object_instance(obj_key, obj_key, obj, obj.matrix_world)
            if sync:
                self.objects_sync.instantiate_object_instance_as_mesh(obj_key, sync)
        else:
            self.objects_sync.update_object_transform(obj_key, obj)

    def update_object_materials(self, obj_key, obj):
        materials = get_materials(obj)
        for material_index, material in enumerate(materials):
            self.update_object_material(obj_key, material, material_index)

    def update_object_materials_if_material_was_updated(self, obj_key, obj):
        materials = get_materials(obj)
        for material_index, material in enumerate(materials):
            mat_key = get_object_key(material)
            if self.was_material_updated(mat_key):
                self.update_object_material(obj_key, material, material_index)

    def update_object_material(self, obj_key, material, material_index):
        if material not in self.objects_needing_material_update:
            self.objects_needing_material_update[material] = set()
        self.objects_needing_material_update[material].add((obj_key, material_index))


class SceneExport:
    def __init__(self, scene, scene_synced, preview=False, types_geometry=('MESH', 'CURVE', 'SURFACE', 'FONT', 'META')):
        log_sync(self, '__init__')
        self.preview = preview
        self.scene = scene
        self.scene_synced = scene_synced
        self.types_geometry = types_geometry
        self.meshes_extracted = {}
        self.lamps_added = set()
        self.visible_objects = set()
        self.next_matrices = {}
        self.profile = False
        self.motion_blur_frame = -1

        self.is_material_preview = False

        self.objects_sync = ObjectsSync(weakref.proxy(self))

        self.environment_settings = {
            'enable': False,
            'gizmo_rotation': (0, 0, 0),
            'ibl': {
                'color': (0, 0, 0),
                'intensity': 1.0,
                'use_ibl_map': False,
                'maps': {
                    'override_background': False,
                }
            }
        }

        self.environment_settings_pre = self.environment_settings

        self.environment_exporter = EnvironmentExportState()
        self.environment_exporter.scene_synced = scene_synced

    @call_logger.logged
    def __del__(self):
        self.scene_synced = None
        self.environment_exporter.scene_synced = None

    @call_logger.logged
    def to_mesh(self, obj):
        key = get_object_key(obj)
        if key in self.meshes_extracted:
            log_sync("to_mesh: found in cache")
            return self.meshes_extracted[key]
        scene = self.scene

        mesh = get_blender_mesh(scene, obj, preview=self.preview)
        if not mesh:
            log_sync("to_mesh: get_blender_mesh returned None")
            return None
        try:
            extracted_mesh = extract_mesh(mesh, 1)
            if not extracted_mesh:
                return None
            # mesh might not be added because it has not polygons
            self.meshes_extracted[key] = extracted_mesh
            return extracted_mesh
        finally:
            bpy.data.meshes.remove(mesh)  # cleanup

    @call_logger.logged
    def remove_mesh_data_from_cache(self, obj_key):
        if obj_key in self.meshes_extracted:
            del self.meshes_extracted[obj_key]

    def get_object_motion_blur(self, mesh_sync: 'MeshSync'):
        scene = self.scene
        if scene.rpr.render.motion_blur and \
                scene.rpr.render.motion_blur_type == 'GEOMETRY' and \
                scene.camera != None:
            if self.motion_blur_frame != scene.frame_current:
                self.motion_blur_frame = scene.frame_current
                self.next_matrices = {}
            return (mesh_sync.object_mesh.blender_obj.matrix_world,
                    self.get_next_matrix(mesh_sync.object_mesh.blender_obj),
                    scene.rpr.render.motion_blur_geometry_scale * 0.01 * scene.render.fps / 100.0)

    def export(self):
        if self.profile:
            s = cProfile.runctx("self._export()", globals(), locals(), sort='cumulative')
        else:
            self._export()

    def _export(self):
        for _ in self.export_iter():
            pass

    def export_iter(self):
        """Export scene iteratively, so it can be cancelled on every iteration, returns name
        of the object being processed.
        """
        try:
            yield from self._export_objects(self.scene.objects)
            yield '<environment>'
            self.sync_environment()
        except:
            logging.critical(traceback.format_exc(), tag='export')
            raise
        finally:
            import rprblender.images
            logging.info(rprblender.images.image_cache.stats.format_current(), tag='image_cache')

    def export_preview(self, is_icon):
        logging.debug('export_preview...')
        self.is_material_preview = True
        self.export()
        self.scene_synced.add_back_preview(is_icon)

    def export_objects(self, objects):
        for _ in self._export_objects(objects):
            pass

    def _export_objects(self, objects):
        self.visible_objects = {get_object_key(obj): obj.type for obj in self.filter_scene_objects_visible(objects)}
        yield from self.sync_updated_objects(set(self.visible_objects))
        self.scene_objects = set(objects)

    def _export_objects_plain(self, objects):
        """this is simple export of all objects, without using 'sync' method, left for reference"""
        log_sync('_export_objects')
        scene_synced = self.scene_synced
        time_start = time.clock()

        duplicators = []

        for obj in objects:
            yield obj.name
            object_key = get_object_key(obj)
            log_sync(obj, obj.type, object_key)
            object_type = obj.type

            visible = self.is_scene_object_visible(obj)

            log_sync('VISIBLE' if visible else 'NOT VISIBLE')

            if object_type in self.types_geometry:
                if visible:
                    sync = self.objects_sync.add_object_instance(object_key, object_key, obj, obj.matrix_world)
                    if sync:
                        self.objects_sync.instantiate_object_instance_as_mesh(object_key, sync)

            if 'LAMP' == object_type:
                if not self.is_material_preview and visible:
                    self.add_lamp(obj)

            if 'NONE' != obj.dupli_type:
                if visible:
                    log_sync(obj.dupli_type)
                    assert obj.is_duplicator

                    duplicators.append(obj)

        for obj in duplicators:
            for key, dupli in self.iter_dupli_from_duplicator(obj):
                if self.is_prototype_visible(dupli.object):
                    self.objects_sync.add_instance(get_object_key(obj), key, dupli)

        yield "materials"

        self.objects_sync.init_materials()

        self.visible_objects = {get_object_key(obj): obj.type for obj in self.filter_scene_objects_visible(objects)}
        log_sync("visible_objects", len(self.visible_objects), self.visible_objects)

        self.scene_objects = set(objects)
        self.scene_objects = set(self.scene.objects)
        log_sync("self.scene_objects", len(self.scene_objects), self.scene_objects)

    def iter_dupli_from_duplicator(self, duplicator):
        duplicator.dupli_list_create(self.scene, settings='RENDER')
        try:
            for dupli in duplicator.dupli_list:
                if dupli.object.type in self.types_geometry:
                    yield self.get_instance_key(duplicator, dupli), dupli
        finally:
            duplicator.dupli_list_clear()

    def add_lamp(self, obj):
        key = get_object_key(obj)
        self.lamps_added.add(key)
        self.scene_synced.add_lamp(key, obj)

    def remove_lamp(self, key):
        if key in self.lamps_added:
            self.lamps_added.remove(key)
            self.scene_synced.remove_lamp(key)

    def get_all_blender_objects_visible_in_viewport(self):
        # NOTE: 'hide_render' for render visibility
        return set(o for o in bpy.data.objects
                   if not o.hide_render and not o.hide and self.is_blender_object_visible_in_viewport(o))

    def filter_scene_objects_visible(self, objects):
        # NOTE: 'hide_render' for render visibility
        return set(o for o in objects if self.is_scene_object_visible(o))

    def is_blender_object_visible_in_viewport(self, obj):
        return not obj.hide and self.is_blender_object_in_included_layer(obj)

    def is_blender_object_visible_in_render(self, obj):
        return not obj.hide_render and self.is_blender_object_in_included_layer(obj)

    def is_scene_object_visible(self, obj):
        if self.is_material_preview:
            return obj.is_visible(self.scene) and not obj.hide_render and obj.name.startswith('preview')
        if self.preview:
            visible = self.is_blender_object_visible_in_viewport(obj)
        else:
            visible = self.is_blender_object_visible_in_render(obj)
        return visible

    def is_prototype_visible(self, obj):
        if self.preview:
            return not obj.hide
        else:
            return not obj.hide_render

    def is_blender_object_in_included_layer(self, obj):
        obj_layers = np.array(obj.layers, dtype=bool)
        scene_layers = np.array(self.scene.layers, dtype=bool)
        excluded_layers = np.array(self.scene.render.layers.active.layers_exclude, dtype=bool)

        return np.any(np.logical_and(
            np.logical_and(obj_layers, scene_layers),
            np.logical_not(excluded_layers)))

    def get_next_matrix(self, obj):
        parent_movement = Matrix.Identity(4)
        if obj.parent != None:
            parent_movement = self.get_next_matrix(obj.parent) * obj.parent.matrix_world.inverted()

        id = get_object_key(obj)
        matrix = obj.matrix_world.copy()
        if self.next_matrices.get(id) == None:
            if obj.animation_data is not None and obj.animation_data.action is not None:
                obj_curves = obj.animation_data.action.fcurves
                logging.debug("rotation type", obj.rotation_mode)
                x = 0.0
                y = 0.0
                z = 0.0
                w = 0.0
                if obj.rotation_mode == 'QUATERNION':
                    w_curve = obj_curves.find('rotation_quaternion', index=0)
                    x_curve = obj_curves.find('rotation_quaternion', index=1)
                    y_curve = obj_curves.find('rotation_quaternion', index=2)
                    z_curve = obj_curves.find('rotation_quaternion', index=3)

                    if w_curve:
                        w = w_curve.evaluate(self.scene.frame_current + 1)
                    if x_curve:
                        x = x_curve.evaluate(self.scene.frame_current + 1)
                    if y_curve:
                        y = y_curve.evaluate(self.scene.frame_current + 1)
                    if z_curve:
                        z = z_curve.evaluate(self.scene.frame_current + 1)

                    # if no axis then just get axis from current frame
                    if not x_curve and not y_curve and not z_curve:
                        x = obj.rotation_quaternion[1]
                        y = obj.rotation_quaternion[2]
                        z = obj.rotation_quaternion[3]
                    logging.debug("rotation values", x, y, z, w)
                    matrix = Quaternion((w, x, y, z)).to_matrix().to_4x4()

                elif obj.rotation_mode == 'AXIS_ANGLE':
                    w_curve = obj_curves.find('rotation_axis_angle', index=0)
                    x_curve = obj_curves.find('rotation_axis_angle', index=1)
                    y_curve = obj_curves.find('rotation_axis_angle', index=2)
                    z_curve = obj_curves.find('rotation_axis_angle', index=3)

                    if w_curve:
                        w = w_curve.evaluate(self.scene.frame_current + 1)
                    if x_curve:
                        x = x_curve.evaluate(self.scene.frame_current + 1)
                    if y_curve:
                        y = y_curve.evaluate(self.scene.frame_current + 1)
                    if z_curve:
                        z = z_curve.evaluate(self.scene.frame_current + 1)

                    # if no axis then just get axis from current frame
                    if not x_curve and not y_curve and not z_curve:
                        x = obj.rotation_axis_angle[1]
                        y = obj.rotation_axis_angle[2]
                        z = obj.rotation_axis_angle[3]
                    logging.debug("rotation values", x, y, z, w)
                    matrix = Matrix.Rotation(w, 4, mathutils.Vector((x, y, z)))
                else:
                    x_curve = obj_curves.find('rotation_euler', index=0)
                    y_curve = obj_curves.find('rotation_euler', index=1)
                    z_curve = obj_curves.find('rotation_euler', index=2)
                    if x_curve:
                        x = x_curve.evaluate(self.scene.frame_current + 1)
                    if y_curve:
                        y = y_curve.evaluate(self.scene.frame_current + 1)
                    if z_curve:
                        z = z_curve.evaluate(self.scene.frame_current + 1)
                    logging.debug("rotation values", x, y, z)
                    matrix = Euler((x, y, z), 'XYZ').to_matrix().to_4x4()

                logging.debug("rotation matrix", matrix)

                scale = mathutils.Vector()
                curve = obj_curves.find('scale', 0)
                if curve:
                    scale.x = curve.evaluate(self.scene.frame_current + 1)
                else:
                    scale.x = obj.scale[0]
                curve = obj_curves.find('scale', 1)
                if curve:
                    scale.y = curve.evaluate(self.scene.frame_current + 1)
                else:
                    scale.y = obj.scale[1]
                curve = obj_curves.find('scale', 2)
                if curve:
                    scale.z = curve.evaluate(self.scene.frame_current + 1)
                else:
                    scale.z = obj.scale[2]

                logging.debug("scale", scale)

                matrix *= mathutils.Matrix.Scale(scale.x, 4, mathutils.Vector((1.0, 0.0, 0.0)))
                matrix *= mathutils.Matrix.Scale(scale.y, 4, mathutils.Vector((0.0, 1.0, 0.0)))
                matrix *= mathutils.Matrix.Scale(scale.z, 4, mathutils.Vector((0.0, 0.0, 1.0)))

                curve = obj_curves.find('location', 0)
                if curve:
                    matrix[0][3] = curve.evaluate(self.scene.frame_current + 1)
                    logging.debug("locationX", matrix[0][3])
                else:
                    matrix[0][3] = obj.matrix_world[0][3]
                curve = obj_curves.find('location', 1)
                if curve:
                    matrix[1][3] = curve.evaluate(self.scene.frame_current + 1)
                    logging.debug("locationY", matrix[1][3])
                else:
                    matrix[1][3] = obj.matrix_world[1][3]
                curve = obj_curves.find('location', 2)
                if curve:
                    matrix[2][3] = curve.evaluate(self.scene.frame_current + 1)
                    logging.debug("locationZ", matrix[2][3])
                else:
                    matrix[2][3] = obj.matrix_world[2][3]
            self.next_matrices[id] = parent_movement * matrix
        # How to check frame calculation. We don't use this simple way to get next matrix beacouse we don't want to move current frame
        # logging.debug("was matrix", obj.matrix_world)
        # logging.debug("now matrix", matrix)
        # self.scene.frame_set(self.scene.frame_current + 1)
        # matrix2 = obj.matrix_world.copy();
        # logging.debug("test matrix", matrix2)
        # self.scene.frame_set(self.scene.frame_current - 1)

        return self.next_matrices[id]

    def extract_settings(self, settings, settings_keys):
        result_settings = {}
        for key, value in settings_keys.items():
            settings_value = getattr(settings, key)
            if value is not None:
                if callable(value):
                    # convert
                    result_settings[key] = value(settings_value)
                else:
                    result_settings[key] = self.extract_settings(settings_value, value)
            else:
                result_settings[key] = settings_value
        return result_settings

    def sync(self):
        log_sync('sync!')

        try:
            with TimedContext("sync"):
                if self.profile:
                    s = cProfile.runctx("self._sync()", globals(), locals(), sort='cumulative')
                else:
                    self._sync()
        except:
            logging.critical(traceback.format_exc(), tag='export')
            raise

    def sync_environment_settings(self, env):

        if env:
            environment_extracted_settings = self.extract_settings(env, self.get_env_settings_keys())
        else:
            environment_extracted_settings = {
                'enable': False,
            }
        self.set_environment_settings(environment_extracted_settings)

    def set_environment_settings(self, environment_extracted_settings):
        logging.debug('set_environment_settings: ', environment_extracted_settings, tag='sync')
        self.environment_settings_pre = environment_extracted_settings

    def _sync(self):
        logging.debug("export.sync")

        self.need_scene_reset = False

        self.sync_environment()

        visible_objects = {get_object_key(obj): obj.type for obj in
                           self.filter_scene_objects_visible(bpy.context.scene.objects)}
        log_sync("visible_objects", len(visible_objects), visible_objects)
        log_sync("self.visible_objects", len(self.visible_objects), self.visible_objects)

        objects_not_visible_anymore = {k: self.visible_objects[k] for k in
                                       set(self.visible_objects) - set(visible_objects)}
        objects_just_became_visible = {k: visible_objects[k] for k in set(visible_objects) - set(self.visible_objects)}

        if bpy.data.materials.is_updated:
            log_sync('bpy.data.materials.is_updated')
            for mat in bpy.data.materials:
                log_sync('  export.sync : material %s, is_updated: %s' % (mat.name, mat.is_updated))
                log_sync(mat)
                tree = mat.node_tree
                if not tree:
                    continue

                log_sync('  tree :', tree)
                # NOTE: mat.is_updated here is needed to catch link changes in the material node tree
                if mat.is_updated or tree.is_updated or tree.is_updated_data:
                    log_sync('  export.sync : material changed %s' % mat.name)
                    objects_for_material = []
                    for obj in bpy.data.objects:
                        if obj.type in self.types_geometry:
                            for material_index, slot in enumerate(obj.material_slots):
                                if slot.material == mat:
                                    objects_for_material.append((get_object_key(obj), material_index))
                    self.objects_sync.update_material(objects_for_material, mat)

        scene_objects = set(self.scene.objects)

        scene_objects_added = scene_objects - self.scene_objects

        # seems we can't keep references anyway data is invalid when object if removed
        # even printing list of removed objects may crash(repr call)
        scene_objects_removed = {get_object_key(obj) for obj in (self.scene_objects - scene_objects)}
        log_sync("scene_objects_removed:", scene_objects_removed)

        self.scene_objects = scene_objects

        self.visible_objects = visible_objects

        for obj_key in scene_objects_removed:
            logging.debug("removing:", obj_key)
            self.remove_lamp(obj_key)
            self.objects_sync.remove_object_instance(obj_key)

        for obj_key, obj_type in objects_not_visible_anymore.items():

            if self.objects_sync.is_duplicator(obj_key):
                self.objects_sync.remove_duplicator_instances(obj_key)

            if obj_key in scene_objects_removed:
                # TODO: handle removal without accessing object data(dereferencing pointer, i.e. obj.type)
                # test this!
                continue
            if obj_type in self.types_geometry:
                self.objects_sync.hide_object(obj_key)
                self.objects_sync.remove_instances_for_prototype(obj_key)

            elif 'LAMP' == obj_type:
                self.scene_synced.hide_lamp(obj_key)

        with TimedContext("sync_updated_objects"):
            log_sync('bpy.data.objects.is_updated', bpy.data.objects.is_updated)
            if bpy.data.objects.is_updated:
                log_sync('scene_objects_added', len(scene_objects_added), scene_objects_added)
                log_sync('objects_just_became_visible', len(objects_just_became_visible), objects_just_became_visible)
                for _ in self.sync_updated_objects(set(scene_objects_added) | set(objects_just_became_visible)):
                    pass

        if objects_just_became_visible:
            logging.debug('objects_just_became_visible:', objects_just_became_visible)
        for obj_key, obj_type in objects_just_became_visible.items():
            if obj_type in self.types_geometry:
                self.objects_sync.show_object(obj_key)
            elif 'LAMP' == obj_type:
                self.scene_synced.show_lamp(obj_key)

        self.sync_motion_blur()

    def sun_and_sky_sync(self, attach, sync):
        logging.debug('sun_and_sky_sync ', tag='sync')
        enable = sync.get('enable')
        if not enable.get_updated_value():
            return

        # parameters declaration (lib functions)
        lib = helpers.render_resources_helper.lib

        lib.set_sun_horizontal_coordinate.argtypes = [ctypes.c_float, ctypes.c_float]
        lib.set_sun_time_location.argtypes = [ctypes.c_float, ctypes.c_float,
                                              ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                              ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                              ctypes.c_float, ctypes.c_bool]
        lib.set_sky_params.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float,
                                       ctypes.c_float,
                                       ctypes.c_void_p, ctypes.c_void_p]

        lib.generate_sky_image.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]

        lib.generate_sky_image.restype = ctypes.c_bool
        lib.get_sun_azimuth.restype = ctypes.c_float

        # set parameters & calculate image
        env_type = sync.get('type')
        type = sync.get('sun_sky', 'type')
        azimuth_was_changed = False

        need_update = type.updated() or env_type.updated()

        if type.get_updated_value() == 'analytical_sky':
            azimuth_var = sync.get('sun_sky', 'azimuth')
            altitude_var = sync.get('sun_sky', 'altitude')
            if azimuth_var.updated() or altitude_var.updated() or need_update:
                logging.debug('set_sun_horizontal_coordinate...', tag='sync')
                lib.set_sun_horizontal_coordinate(math.degrees(azimuth_var.get_updated_value()),
                                                  math.degrees(altitude_var.get_updated_value()))
                azimuth_was_changed = True
        else:
            latitude_var = sync.get('sun_sky', 'latitude')
            longitude_var = sync.get('sun_sky', 'longitude')
            date_year_var = sync.get('sun_sky', 'date_year')
            date_month_var = sync.get('sun_sky', 'date_month')
            date_day_var = sync.get('sun_sky', 'date_day')
            time_hours_var = sync.get('sun_sky', 'time_hours')
            time_minutes_var = sync.get('sun_sky', 'time_minutes')
            time_seconds_var = sync.get('sun_sky', 'time_seconds')
            time_zone_var = sync.get('sun_sky', 'time_zone')
            daylight_savings_var = sync.get('sun_sky', 'daylight_savings')
            if latitude_var.updated() or longitude_var.updated() or \
                date_year_var.updated() or date_month_var.updated() or date_day_var.updated() or \
                time_hours_var.updated() or time_minutes_var.updated() or time_seconds_var.updated() or \
                time_zone_var.updated() or daylight_savings_var.updated() or need_update:
                logging.debug('set_sun_time_location...', tag='sync')
                lib.set_sun_time_location(math.degrees(latitude_var.get_updated_value()),
                                          math.degrees(longitude_var.get_updated_value()),
                                          date_year_var.get_updated_value(), date_month_var.get_updated_value(),
                                          date_day_var.get_updated_value(),
                                          time_hours_var.get_updated_value(), time_minutes_var.get_updated_value(),
                                          time_seconds_var.get_updated_value(),
                                          time_zone_var.get_updated_value(), daylight_savings_var.get_updated_value())
                azimuth_was_changed = True

        filter_color = sync.get('sun_sky', 'filter_color').get_updated_value()
        ground_color = sync.get('sun_sky', 'ground_color').get_updated_value()
        turbidity = sync.get('sun_sky', 'turbidity').get_updated_value()
        sun_glow = sync.get('sun_sky', 'sun_glow').get_updated_value()
        sun_disc = sync.get('sun_sky', 'sun_disc').get_updated_value()
        horizon_height = sync.get('sun_sky', 'horizon_height').get_updated_value()
        horizon_blur = sync.get('sun_sky', 'horizon_blur').get_updated_value()
        saturation = sync.get('sun_sky', 'saturation').get_updated_value()

        filter_color_arr = np.array(filter_color, dtype=np.float32)
        ground_color_arr = np.array(ground_color, dtype=np.float32)
        lib.set_sky_params(turbidity, sun_glow, sun_disc, horizon_height, horizon_blur, saturation,
                           ctypes.c_void_p(filter_color_arr.ctypes.data), ctypes.c_void_p(ground_color_arr.ctypes.data))

        assert not self.environment_exporter.sun_sky_image_buffer is None
        res = lib.generate_sky_image(self.environment_exporter.sun_sky_size,
                                     self.environment_exporter.sun_sky_size,
                                     self.environment_exporter.sun_sky_image_buffer.ctypes.data)
        assert res

        # create environment light
        if attach:
            self.environment_exporter.sun_sky = self.scene_synced.environment_light_create_empty()

        self.environment_exporter.sun_sky.set_image_from_buffer(self.environment_exporter.sun_sky_image_buffer,
                                                                self.environment_exporter.SKY_TEXTURE_BITS_COUNT)
        intensity = sync.get('sun_sky', 'intensity').get_updated_value()
        self.environment_exporter.sun_sky.set_intensity(intensity)

        # set sky rotation
        rotation_var = sync.get('gizmo_rotation')

        if azimuth_was_changed or rotation_var.updated() or attach:
            sun_azimuth = lib.get_sun_azimuth()
            rot = rotation_var.get_updated_value()

            euler_main_rotation = mathutils.Euler((-rot[0], -rot[1], -rot[2]))
            main_matrix = euler_main_rotation.to_matrix()
            euler_azimut_rotation = mathutils.Euler((0, np.pi, -sun_azimuth))
            azimut_matrix = euler_azimut_rotation.to_matrix()
            mat = azimut_matrix * main_matrix

            mat_rot = np.array(mat, dtype=np.float32)
            fixup = np.array([[1, 0, 0],
                              [0, 0, 1],
                              [0, 1, 0]], dtype=np.float32)
            matrix = np.identity(4, dtype=np.float32)
            matrix[:3, :3] = np.dot(fixup, mat_rot)
            matrix_ptr = ffi.cast('float*', matrix.ctypes.data)
            pyrpr.LightSetTransform(self.environment_exporter.sun_sky.core_environment_light, False, matrix_ptr)

        if attach:
            self.environment_exporter.sun_sky.attach()

    @staticmethod
    def get_env_settings_keys():
        env_settings_keys = {
            'enable': None,
            'gizmo_rotation': tuple,
            'type': None,
            'ibl': {
                'color': tuple,
                'intensity': None,
                'use_ibl_map': None,
                ('ibl_image' if versions.is_blender_support_ibl_image() else 'ibl_map'): None,
                'maps': {
                    'override_background': None,
                    'override_background_type': None,
                    ('background_image' if versions.is_blender_support_ibl_image() else 'background_map'): None,
                    'background_color': tuple,
                }
            },
            'sun_sky': {
                'type': None,
                'azimuth': None,
                'altitude': None,
                'latitude': None,
                'longitude': None,
                'date_year': None,
                'date_month': None,
                'date_day': None,
                'time_hours': None,
                'time_minutes': None,
                'time_seconds': None,
                'time_zone': None,
                'daylight_savings': None,
                'turbidity': None,
                'intensity': None,
                'sun_glow': None,
                'sun_disc': None,
                'saturation': None,
                'horizon_height': None,
                'horizon_blur': None,
                'filter_color': tuple,
                'ground_color': tuple,
                'texture_resolution': None,
            }
        }
        return env_settings_keys


    def sync_environment(self):
        logging.debug('sync_environment', tag='sync')

        logging.debug('self.environment_settings_pre: ', self.environment_settings_pre, tag='sync')
        logging.debug('self.environment_settings: ', self.environment_settings, tag='sync')


        if self.environment_settings != self.environment_settings_pre:
            logging.debug('environment_settings NOT equal', self.environment_settings_pre, tag='sync')

            settings_sync = self.filter_environment_light_settings_changes(self.environment_settings,
                                                                           self.environment_settings_pre)
            self.set_environment_light(settings_sync)
            settings_sync.update()

            return True
        return False

    def sync_motion_blur(self):
        for obj in self.scene.objects:
            obj_key = get_object_key(obj)
            if obj_key not in self.visible_objects:
                continue
            if obj.type not in self.types_geometry:
                continue
            if not self.objects_sync.is_object_instantiated_as_mesh_prototype(obj_key):
                continue
            mesh_sync = self.objects_sync.object_instances[obj_key]
            motion_blur = self.get_object_motion_blur(mesh_sync)
            if motion_blur is not None:
                for i in mesh_sync.materials_assigned:
                    self.scene_synced.set_motion_blur((obj_key, i), *motion_blur)
            else:
                for i in mesh_sync.materials_assigned:
                    self.scene_synced.reset_motion_blur((obj_key, i))

    def sync_updated_objects(self, scene_objects_added):
        log_sync('sync_updated_objects', scene_objects_added)

        objects_sync_frame = ObjectsSyncFrame(self, self.objects_sync)

        for obj in self.filter_scene_objects_visible(self.scene.objects):
            yield obj.name
            obj_key = get_object_key(obj)

            if obj_key in scene_objects_added:
                if obj.is_duplicator:
                    objects_sync_frame.add_duplicator(obj)

            if obj.is_updated or obj.is_updated_data or obj_key in scene_objects_added:
                log_sync('object to update:', obj, obj.type, get_object_key(obj),
                         obj.is_updated, obj.is_updated_data or (obj.data and obj.data.is_updated))

                if obj.type in self.types_geometry:

                    objects_sync_frame.add_instances_for_prototype(obj_key)

                    if obj.is_updated_data or (obj.data and obj.data.is_updated):
                        log_sync(
                            'update_mesh_data - obj.is_updated: %s, obj.is_updated_data:%s, obj.data.is_updated: %s' % (
                                obj.is_updated, obj.is_updated_data, (obj.data and obj.data.is_updated)))
                        objects_sync_frame.update_object_data(obj_key, obj)
                    else:
                        objects_sync_frame.update_object_transform(obj_key, obj)

                    self.objects_sync.update_settings(obj_key, obj.rpr_object)

                    objects_sync_frame.update_object_materials(obj_key, obj)

                elif 'LAMP' == obj.type:

                    # TODO: unify this code, about checking if objects was already there
                    # note - this is potentially possible that object with same pointer(id) will be something
                    # completely different
                    if obj_key in self.lamps_added:
                        self.remove_lamp(obj_key)
                    if not self.is_material_preview:
                        self.add_lamp(obj)

                elif 'EMPTY' == obj.type:
                    pass
                else:
                    logging.debug("UNSUPPORTED type for sync, resetting scene")

                if 'NONE' != obj.dupli_type:
                    objects_sync_frame.duplicators_updated.add(obj_key)

        yield 'reinstantiating instances'
        instances_to_readd = {}
        for obj_key, obj in objects_sync_frame.meshes_updated_data.items():
            for instance_key in list(self.objects_sync.instances_added_for_prototype.get(obj_key, [])):
                assert instance_key in self.objects_sync.instances
                instance_sync = self.objects_sync.object_instances[instance_key]
                duplicator_key = self.objects_sync.duplicator_for_instance[instance_key]
                instances_to_readd.setdefault(duplicator_key, []).append((instance_key, instance_sync))
                self.objects_sync.deinstantiate_object_instance_as_mesh(instance_key)

            self.objects_sync.update_object_data(obj_key, obj)

        for duplicator_key, instances in instances_to_readd.items():
            for instance_key, instance_sync in instances:
                self.objects_sync.object_instances[instance_key] = instance_sync
                self.objects_sync.instantiate_object_instance_as_mesh(instance_key, instance_sync)

        objects_sync_frame.create_materials_updated_list()
        # for now we are simply re-creating material if object or material was updated
        # so if one object using a material was updated - so this material needs to be re-assigned for
        # all objects with this material

        for obj in self.scene.objects:
            obj_key = get_object_key(obj)
            objects_sync_frame.update_object_materials_if_material_was_updated(obj_key, obj)

        ########## done ObjectsSyncFrame

        yield 'updating materials'
        log_sync("objects_needing_material_update:", objects_sync_frame.objects_needing_material_update)
        for material, objects in objects_sync_frame.objects_needing_material_update.items():
            yield 'updating materials: %s(%s objects)' % (material.name if material else "<none>", len(objects))
            self.objects_sync.update_material(objects, material)

        yield 'adding new duplicators'
        for obj in objects_sync_frame.duplicators_added:
            yield 'adding new duplicators:'+str(obj)
            for key, dupli in self.iter_dupli_from_duplicator(obj):
                self.objects_sync.add_instance(get_object_key(obj), key, dupli)
                self.objects_sync.update_instance_materials(key)

        yield 'updating duplicators'
        log_sync('duplicators_updated:', objects_sync_frame.duplicators_updated)
        with TimedContext("update duplicators"):
            for obj in self.scene.objects:
                obj_key = get_object_key(obj)

                if obj_key in objects_sync_frame.duplicators_updated:
                    self.objects_sync.sync_duplicator_instances(obj_key, obj)
        yield 'objects ok'

    def get_instance_key(self, duplicator, dupli):
        # different duplis can be instances of the same object and persistent_id differentiates them
        return get_instance_key(duplicator, dupli)

    def filter_environment_light_settings_changes(self, settings_old, environment_settings):
        """"Leave only changes in settings that affect result render(i.e. don't bother with maps
        is whole environment is disabled"""
        sync = SettingsSyncer(settings_old, environment_settings)
        enable = sync.get('enable')

        enable.use_new_value()
        logging.debug(enable, tag='sync')

        if not enable.get_updated_value():
            # don't change anything except one flag if environment is disabled
            return sync

        type = sync.get('type')
        type.use_new_value()

        sync.get('gizmo_rotation').use_new_value()

        if type.get_updated_value() == 'IBL':
            sync.get('ibl', 'intensity').use_new_value()

            use_ibl_map = sync.get('ibl', 'use_ibl_map')
            use_ibl_map.use_new_value()

            if use_ibl_map.get_updated_value():
                # change map only when it's enabled
                ibl_map = sync.get('ibl', 'ibl_image' if versions.is_blender_support_ibl_image() else 'ibl_map')
                ibl_map.use_new_value()
            else:
                color = sync.get('ibl', 'color')
                color.use_new_value()

            override_background = sync.get('ibl', 'maps', 'override_background')
            override_background.use_new_value()

            if override_background.get_updated_value():

                override_background_type = sync.get('ibl', 'maps', "override_background_type")
                override_background_type.use_new_value()

                if override_background_type.get_updated_value() == 'image':
                    background_map = sync.get('ibl', 'maps', 'background_image' if versions.is_blender_support_ibl_image() else 'background_map')
                    background_map.use_new_value()
                else:
                    background_color = sync.get('ibl', 'maps', 'background_color')
                    background_color.use_new_value()

        else:
            sun_sky_type = sync.get('sun_sky', 'type')
            sun_sky_type.use_new_value()

            if sun_sky_type.get_updated_value() == 'analytical_sky':
                sync.get('sun_sky', 'azimuth').use_new_value()
                sync.get('sun_sky', 'altitude').use_new_value()
            else:
                sync.get('sun_sky', 'latitude').use_new_value()
                sync.get('sun_sky', 'longitude').use_new_value()
                sync.get('sun_sky', 'date_year').use_new_value()
                sync.get('sun_sky', 'date_month').use_new_value()
                sync.get('sun_sky', 'date_day').use_new_value()
                sync.get('sun_sky', 'time_hours').use_new_value()
                sync.get('sun_sky', 'time_minutes').use_new_value()
                sync.get('sun_sky', 'time_seconds').use_new_value()
                sync.get('sun_sky', 'time_zone').use_new_value()
                sync.get('sun_sky', 'daylight_savings').use_new_value()

            sync.get('sun_sky', 'turbidity').use_new_value()
            sync.get('sun_sky', 'intensity').use_new_value()
            sync.get('sun_sky', 'sun_glow').use_new_value()
            sync.get('sun_sky', 'sun_disc').use_new_value()
            sync.get('sun_sky', 'saturation').use_new_value()
            sync.get('sun_sky', 'horizon_height').use_new_value()
            sync.get('sun_sky', 'horizon_blur').use_new_value()
            sync.get('sun_sky', 'filter_color').use_new_value()
            sync.get('sun_sky', 'ground_color').use_new_value()
            sync.get('sun_sky', 'texture_resolution').use_new_value()

        return sync

    def set_environment_light(self, sync):
        logging.debug("settings to sync:", sync.synced, tag='sync')

        enable = sync.get('enable')
        type = sync.get('type')

        ibl_needs_attach = False
        background_needs_enable = False

        detach_ibl = False
        detach_sun_sky = False
        attach_ibl = False
        attach_sun_sky = False

        if enable.updated() or type.updated():
            if enable.get_updated_value() or type.updated():
                if type.get_updated_value() == 'IBL':
                    attach_ibl = True
                    detach_sun_sky = True
                else:
                    attach_sun_sky = True
                    detach_ibl = True
            else:
                detach_ibl = True
                detach_sun_sky = True

        logging.debug('detach_ibl: %s, detach_sun_sky: %s, attach_ibl: %s, attach_sun_sky: %s' % (
        detach_ibl, detach_sun_sky, attach_ibl, attach_sun_sky), tag='sync')

        if detach_ibl:
            self.environment_exporter.ibl_detach()
            self.environment_exporter.background_disable()

        if detach_sun_sky:
            self.environment_exporter.sun_sky_destroy_buffer()
            self.environment_exporter.sun_sky_detach()

        if not enable.get_updated_value():
            return

        assert not (attach_ibl and attach_sun_sky)

        if attach_ibl:
            if self.environment_exporter.ibl and not self.environment_exporter.ibl.attached:
                ibl_needs_attach = True
            if self.environment_exporter.background_override and not self.environment_exporter.background_override.enabled:
                background_needs_enable = True

        texture_resolution = sync.get('sun_sky', 'texture_resolution')

        if attach_sun_sky or texture_resolution.updated():
            self.environment_exporter.sun_sky_create_buffer(texture_resolution.get_updated_value())

        if type.get_updated_value() != 'IBL':
            self.sun_and_sky_sync(attach_sun_sky, sync)
            return

        use_ibl_map = sync.get('ibl', 'use_ibl_map')
        ibl_map = sync.get('ibl', 'ibl_image' if versions.is_blender_support_ibl_image() else 'ibl_map')
        intensity = sync.get('ibl', 'intensity')

        rotation = sync.get('gizmo_rotation')

        if ibl_map.updated() or (use_ibl_map.updated() and use_ibl_map.get_updated_value()):
            self.environment_exporter.ibl_detach()
            self.environment_exporter.ibl = self.scene_synced.environment_light_create(ibl_map.get_updated_value())
            ibl_needs_attach = True

        color = sync.get('ibl', 'color')
        if color.updated() or (use_ibl_map.updated() and not use_ibl_map.get_updated_value()):
            self.environment_exporter.ibl_detach()
            self.environment_exporter.ibl = \
                self.scene_synced.environment_light_create_color(color.get_updated_value())
            ibl_needs_attach = True
        else:
            if use_ibl_map.updated():
                if use_ibl_map.get_updated_value():
                    ibl_needs_attach = True
                else:
                    self.environment_exporter.ibl_detach()

        if ibl_needs_attach:
            self.environment_exporter.ibl.attach()
            logging.debug("ibl.attach ok", tag='sync')

        if self.environment_exporter.ibl:
            ibl = self.environment_exporter.ibl
            ibl.set_intensity(intensity.get_updated_value())

        override_background = sync.get('ibl', 'maps', 'override_background')
        override_background_type = sync.get('ibl', 'maps', "override_background_type")
        background_map = sync.get('ibl', 'maps', 'background_image' if versions.is_blender_support_ibl_image() else 'background_map')
        background_color = sync.get('ibl', 'maps', 'background_color')

        if override_background.updated() \
            or override_background_type.updated() \
            or background_map.updated() \
            or background_color.updated():

            if override_background.get_updated_value():

                if override_background_type.updated() or background_map.updated() or background_color.updated():
                    self.environment_exporter.background_disable()
                    if override_background_type.get_updated_value() == "image":
                        self.environment_exporter.background_override = \
                            self.scene_synced.background_create(background_map.get_updated_value())
                    else:
                        self.environment_exporter.background_override = \
                            self.scene_synced.background_create_color(background_color.get_updated_value())

                background_needs_enable = True

            else:
                background_needs_enable = False
                self.environment_exporter.background_disable()

        if background_needs_enable:
            self.scene_synced.background_set(self.environment_exporter.background_override)

        if self.environment_exporter.ibl:
            self.environment_exporter.ibl.set_rotation(rotation.get_updated_value())

        if self.environment_exporter.background_override:
            self.environment_exporter.background_override.set_rotation(rotation.get_updated_value())


class SettingsSyncer:
    def __init__(self, old, new):
        self.new = new
        self.old = old
        self.synced = {}
        self.synced_paths = []

    def get(self, *path):
        return SettingsSync(self.old, self.new, self.synced, self.synced_paths, path)

    def update(self):
        logging.debug('update:', self.old, self.synced, tag='sync')
        for path in self.synced_paths:
            logging.debug(path, tag='sync')
            SettingsSync.set_value_from_path(
                self.old, path,
                SettingsSync.get_value_from_path(self.synced, path))


class SettingsSync:
    def __init__(self, old, new, synced, synced_paths, path):
        self.new = new
        self.old = old
        self.synced = synced
        self.path = path
        self.synced_paths = synced_paths

    def __str__(self):
        return 'SettingsSync: %r -> %r, (sync: %s) (path: %s)' % (
            self.get_old_value('<none>'), self.get_new_value('<none>'),
            self.updated(),
            '/'.join(self.path))

    def set_synced_value(self, value):
        self.set_value_from_path(self.synced, self.path, value)
        self.synced_paths.append(self.path)

    def updated(self):
        return self.has_value_from_path(self.synced, self.path)

    def get_updated_value(self):
        if self.has_value_from_path(self.synced, self.path):
            return self.get_value_from_path(self.synced, self.path)
        return self.get_value_from_path(self.old, self.path)

    def is_same(self):
        logging.debug('is_same', self.has_old_value(), self.has_new_value(), tag='sync')
        if self.has_old_value() != self.has_new_value():
            return False
        if self.has_old_value():
            return self.old_value == self.new_value
        else:
            return True

    old_value = property(fget=lambda self: self.get_value_from_path(self.old, self.path))
    new_value = property(fget=lambda self: self.get_value_from_path(self.new, self.path))

    def has_old_value(self):
        logging.debug('has_old_value', self.old, self.path, tag='sync')

        return self.has_value_from_path(self.old, self.path)

    def has_new_value(self):
        return self.has_value_from_path(self.new, self.path)

    def get_old_value(self, default=None):
        if self.has_value_from_path(self.old, self.path):
            return self.old_value
        return default

    def get_new_value(self, default=None):
        if self.has_value_from_path(self.new, self.path):
            return self.new_value
        return default

    def requested_change(self):
        return self.has_new_value() and not self.is_same()

    def use_new_value(self):
        logging.debug('use_new_value', self, tag='sync')
        if self.requested_change():
            self.set_synced_value(self.get_new_value())
            return True
        return False

    @staticmethod
    def get_value_from_path(settings, path):
        for p in path:
            settings = settings[p]
        return settings

    @staticmethod
    def has_value_from_path(settings, path):
        if settings is None:
            return False
        for p in path:
            if p not in settings:
                return False
            settings = settings[p]
        return True

    @staticmethod
    def set_value_from_path(settings, path, value):
        for p in path[:-1]:
            settings = settings.setdefault(p, {})
        settings[path[-1]] = value


class MeshRaw:
    vertices = None  # type: np.ndarray
    normals = None
    faces_list = None

    loop_indices = None
    uv_layer_uvs = None

    faces_materials = None

    faces_use_smooth = None
    faces_normals = None

    loop_normals = None
    loop_vertex_indices = None

    tessface_count = None
    tessface_vertices = None
    tessface_split_normals = None
    tessface_uv_textures = None

    def __str__(self):
        return str({
            'tessface_count': self.tessface_count,
            'tessface_vertices': self.tessface_vertices,
            'tessface_split_normals': self.tessface_split_normals,
        })


def get_attribute_as_array(collection, attribute_name, dtype, attribute_size=None):
    arr = np.empty(len(collection) * (attribute_size if attribute_size else 1), dtype=dtype)
    collection.foreach_get(attribute_name, arr)
    if not attribute_size:
        return arr
    return arr.reshape(-1, attribute_size)


@call_logger.logged
def extract_mesh_raw(mesh: bpy.types.Mesh):
    """ Extract raw data from Blender mesh to numpy arrays(i.e. something that is
    fast to access from C/C++), without any conversion, fastest way possible"""
    result = MeshRaw()

    result.vertices = get_attribute_as_array(mesh.vertices, 'co', np.float32, 3)

    result.tessface_count = len(mesh.tessfaces)

    # blender/source/blender/makesdna/DNA_meshdata_types.h
    # /*tessellation face, see MLoop/MPoly for the real face data*/
    # typedef struct MFace {
    #     unsigned int v1, v2, v3, v4;
    #     short mat_nr;
    #     char edcode, flag;  /* we keep edcode, for conversion to edges draw flags in old files */
    # } MFace;
    tface_dtype = np.dtype([('v', '|i4', 4), ('mat_nr', '|i2'), ('edcode', '|i1'), ('flag', '|i1')])

    # /*tessellation uv face data*/
    # typedef struct MTFace {
    #     float uv[4][2];
    #     struct Image *tpage;
    #     char flag, transp;
    #     short mode, tile, unwrap;
    # } MTFace;
    mtface_dtype = np.dtype([('uv', '|f4', (4, 2)), ('tpage', '|i8'), ('flag', '|i1'),
                             ('transp', '|i1'),
                             ('mode', '|i2'), ('tile', '|i2'), ('unwrap]', '|i2')])
    # assert mtface_dtype.fields['tpage'].itemsize

    tessfaces_bytes = np.ctypeslib.as_array(
        ctypes.cast(mesh.tessfaces[0].as_pointer(), ctypes.POINTER(ctypes.c_int8)),
        shape=(result.tessface_count * tface_dtype.itemsize,))

    tessfaces_view = tessfaces_bytes.view(dtype=tface_dtype)

    # tessfaces has 4 vertices, 0(zero) in the last vertex indicates that this is not quad but triangle
    # for export speed we just always use quads(Core supports them) just fixing the last index for triangles
    tessquads = tessfaces_view['v']
    isquad = tessquads[:, 3] != 0
    triangles = tessquads.copy()
    triangles[:, 3] = triangles[:, 0]  # make triangle from quad by setting last vertex to first
    result.tessface_vertices = np.where(isquad[:, np.newaxis], tessquads, triangles)

    split_normals_raw = get_attribute_as_array(mesh.tessfaces, 'split_normals', np.float32, 12).reshape(-1, 4, 3)
    result.tessface_split_normals = split_normals_raw.reshape(-1, 3)

    result.faces_materials = tessfaces_view['mat_nr'].copy()

    if mesh.tessface_uv_textures.active is not None:
        uvs_bytes = np.ctypeslib.as_array(
            ctypes.cast(mesh.tessface_uv_textures.active.data[0].as_pointer(), ctypes.POINTER(ctypes.c_int8)),
            shape=(result.tessface_count * mtface_dtype.itemsize,))

        uvs_view = uvs_bytes.view(dtype=mtface_dtype)
        # NOTE: 'copy' is REQUIRED here because we've constructed
        # uv view from a DNA pointer which we don't own and it ca go away(and hard to repro)
        # see AMDBLENDER-552
        result.tessface_uv_textures = uvs_view['uv'].reshape(-1, 2).copy()

    return result


def extract_mesh(mesh: bpy.types.Mesh, scale=1.0):
    if not mesh.tessfaces:
        return None
    return prepare_mesh(extract_mesh_raw(mesh), scale, use_auto_smooth=mesh.use_auto_smooth)


def prepare_mesh(mesh_raw: MeshRaw, scale, use_auto_smooth=False):
    vertices = mesh_raw.vertices * scale

    faces_counts = np.array([len(f) for f in mesh_raw.tessface_vertices], dtype=np.int32)

    indices = np.array(list(itertools.chain(*mesh_raw.tessface_vertices)), dtype=np.int32).flatten()

    if mesh_raw.tessface_uv_textures is not None:
        uvs = mesh_raw.tessface_uv_textures
    else:
        uvs = np.full((np.sum(faces_counts), 2), (0, 0), dtype=np.float32)

    normals_new = mesh_raw.tessface_split_normals

    assert len(normals_new) == len(indices), (len(normals_new), len(indices), len(faces_counts))
    assert len(uvs) == len(indices)

    result = dict(
        type='MESH',
        data=dict(
            vertices=vertices,
            normals=normals_new,
            uvs=uvs,
            vertex_indices=indices,
            indices=np.arange(len(indices), dtype=np.int32),
            faces_counts=faces_counts,
            faces_materials=mesh_raw.faces_materials,
        )
    )
    return result


@call_logger.logged
def extract_submesh(mesh, material_index, scale):
    # assert {3} == set(np.unique(mesh['data']['faces_counts']))


    if {material_index} == set(np.unique(mesh['data']['faces_materials'])):
        return mesh

    material_faces = material_index == mesh['data']['faces_materials']

    indices = mesh['data']['indices'].reshape(-1, 4)[material_faces].flatten()
    vertex_indices = mesh['data']['vertex_indices'].reshape(-1, 4)[material_faces].flatten()

    faces_counts = np.full(np.count_nonzero(material_faces), 4, dtype=np.int32)

    vertices = mesh['data']['vertices']

    result = dict(
        type='MESH',
        data=dict(
            vertices=vertices,
            normals=mesh['data']['normals'],
            uvs=mesh['data']['uvs'],
            vertex_indices=vertex_indices,
            indices=indices,
            faces_counts=faces_counts,
        )
    )
    return result


def get_blender_mesh(scene, obj: bpy.types.Object, preview=False):
    mesh = obj.to_mesh(scene, True, 'PREVIEW' if preview else 'RENDER')
    if not mesh:
        return None
    mesh.calc_normals_split()
    mesh.calc_tessface()
    return mesh

    bm = bmesh.new()
    try:

        if 'MESH' == obj.type:
            # Blender 2.77 - only MESH supports this
            bm.from_object(obj, scene, deform=True, render=not preview)
        else:
            mesh = obj.to_mesh(scene, True, 'PREVIEW' if preview else 'RENDER')
            if not mesh:
                return None
            bm.from_mesh(mesh)
            bpy.data.meshes.remove(mesh)

        # triangulate all polygons as Core doesn't support ngons with facecount >4
        bmesh.ops.triangulate(bm, faces=bm.faces)
        mesh = bpy.data.meshes.new(name='rpr.temp')
        bm.to_mesh(mesh)

        if 'MESH' == obj.type:
            # copy auto_smooth flags and calculate normals(for auto_smooth to apply)
            mesh.use_auto_smooth = obj.data.use_auto_smooth
            mesh.auto_smooth_angle = obj.data.auto_smooth_angle
            mesh.calc_normals_split()

    finally:
        bm.free()
        del bm
    return mesh
