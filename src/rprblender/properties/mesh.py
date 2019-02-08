import numpy as np
import math

import bpy
import pyrpr

from rprblender import utils
from rprblender.utils import logging
from . import RPR_Properties
import rprblender.utils.mesh as mesh_ut


log = logging.Log(tag='Mesh')


class RPR_MeshProperties(RPR_Properties):
    ''' Properties for mesh '''

    def sync(self, rpr_context, obj_instance: bpy.types.DepsgraphObjectInstance):
        ''' sync the mesh '''
        mesh = self.id_data
        obj = obj_instance.object if isinstance(obj_instance, bpy.types.DepsgraphObjectInstance) else obj_instance

        mesh_key = utils.key(mesh)
        key = utils.key(obj_instance)

        rpr_mesh = rpr_context.meshes.get(mesh_key, None)
        if rpr_mesh:
            instance_name = "%s/%s" % (mesh.name, obj.name)
            log("Syncing instance: %s" % instance_name)

            rpr_shape = rpr_context.create_instance(key, rpr_mesh)
            rpr_shape.set_name(instance_name)

        else:
            log("Syncing mesh: %s" % mesh.name)
            data = mesh_ut.get_mesh_data(mesh)
            rpr_shape = rpr_context.create_mesh(
                key, mesh_key,
                data.vertices, data.normals, data.uvs,
                data.vertex_indices, data.normal_indices, data.uv_indices,
                data.num_face_vertices
            )

            self.assign_materials(rpr_context, rpr_shape, obj.material_slots)

        rpr_context.scene.attach(rpr_shape)
        rpr_shape.set_transform(utils.get_transform(obj_instance))

        rpr_shape.set_visibility_primary_only(obj.rpr.visibility_in_primary_rays)
        rpr_shape.set_visibility_in_specular(obj.rpr.reflection_visibility)
        rpr_shape.set_visibility_ex("visible.reflection", obj.rpr.reflection_visibility)
        rpr_shape.set_visibility_ex("visible.reflection.glossy", obj.rpr.reflection_visibility)
        rpr_shape.set_shadow_catcher(obj.rpr.shadowcatcher)
        rpr_shape.set_shadow(obj.rpr.shadows)

        if obj.rpr.subdivision:
            # convert factor from size of subdivision in pixel to RPR
            # RPR wants the subdivision factor as the "number of faces per pixel"
            # the setting gives user the size of face in number pixels.
            # rpr internally does: subdivision size in pixel = 2^factor  / 16.0
            factor = int(math.log2(1 / (16.0 * obj.rpr.subdivision_factor)))

            rpr_shape.subdivision = {
                'factor': factor,
                'boundary': pyrpr.SUBDIV_BOUNDARY_INTERFOP_TYPE_EDGE_AND_CORNER if obj.rpr.subdivision_boundary_type == 'EDGE_CORNER' else
                            pyrpr.SUBDIV_BOUNDARY_INTERFOP_TYPE_EDGE_ONLY,
                'crease_weight': obj.rpr.subdivision_crease_weight
            }

    def sync_update(self, rpr_context, obj, is_updated_geometry, is_updated_transform):
        mesh = self.id_data
        log("Updating mesh: %s" % mesh.name)

        key = utils.key(obj)
        rpr_shape = rpr_context.objects.get(key, None)
        if rpr_shape:
            if is_updated_geometry:
                rpr_context.remove_object(key)
                self.sync(rpr_context, obj)
                return True

            if is_updated_transform:
                rpr_shape.set_transform(utils.get_transform(obj))
                return True

            return self.assign_materials(rpr_context, rpr_shape, obj.material_slots)

        else:
            self.sync(rpr_context, obj)
            return True

        return False

    def assign_materials(self, rpr_context, rpr_shape, material_slots):
        if len(material_slots) == 0:
            return False

        mesh = self.id_data

        material_indices = np.array([tri.material_index for tri in mesh.loop_triangles], dtype=np.int32)
        material_unique_indices = np.unique(material_indices)
        for i in material_unique_indices:
            slot = material_slots[i]

            log("Syncing material '%s'" % slot.name, slot)

            if not slot.material:
                continue

            rpr_material = slot.material.rpr.sync(rpr_context)

            if rpr_material:
                if len(material_unique_indices) == 1:
                    rpr_shape.set_material(rpr_material)
                else:
                    # It is important not to remove previous unused materials here, because core could crash.
                    # They will be in memory till mesh exists.
                    face_indices = np.array(np.where(material_indices == i)[0], dtype=np.int32)
                    rpr_shape.set_material_faces(rpr_material, face_indices)

        return True

    @classmethod
    def register(cls):
        log("Register")
        bpy.types.Mesh.rpr = bpy.props.PointerProperty(
            name="RPR Mesh Settings",
            description="RPR object settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Unregister")
        del bpy.types.Mesh.rpr
