import numpy as np
import bpy

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
        obj = obj_instance.object

        rpr_mesh = rpr_context.meshes.get(utils.key(mesh), None)
        if rpr_mesh:
            instance_name = "%s/%s" % (mesh.name, obj.name)
            log("Syncing instance: %s" % instance_name)

            rpr_shape = rpr_context.create_instance(utils.key(obj_instance), rpr_mesh)
            rpr_shape.set_name(instance_name)

        else:
            log("Syncing mesh: %s" % mesh.name)
            data = mesh_ut.get_mesh_data(mesh)
            rpr_shape = rpr_context.create_mesh(
                utils.key(mesh),
                data.vertices, data.normals, data.uvs,
                data.vertex_indices, data.normal_indices, data.uv_indices,
                data.num_face_vertices
            )

            if len(obj.material_slots) > 0:
                material_indices = np.array([tri.material_index for tri in mesh.loop_triangles], dtype=np.int32)
                material_unique_indices = np.unique(material_indices)
                for i in material_unique_indices:
                    slot = obj.material_slots[i]

                    log("Syncing material '%s'" % slot.name, slot)

                    if not slot.material:
                        continue

                    rpr_material = slot.material.rpr.sync(rpr_context)

                    if rpr_material:
                        if len(material_unique_indices) == 1:
                            rpr_shape.set_material(rpr_material)
                        else:
                            face_indices = np.array(np.where(material_indices == i)[0], dtype=np.int32)
                            rpr_shape.set_material_faces(rpr_material, face_indices)

        rpr_context.scene.attach(rpr_shape)
        rpr_shape.set_transform(utils.get_transform(obj_instance))

        rpr_shape.set_visibility_primary_only(obj.rpr.visibility_in_primary_rays)
        rpr_shape.set_visibility_in_specular(obj.rpr.reflection_visibility)
        rpr_shape.set_visibility_ex("visible.reflection", obj.rpr.reflection_visibility)
        rpr_shape.set_visibility_ex("visible.reflection.glossy", obj.rpr.reflection_visibility)
        rpr_shape.set_shadow_catcher(obj.rpr.shadowcatcher)
        rpr_shape.set_shadow(obj.rpr.shadows)

    def sync_update(self, rpr_context, obj, is_updated_geometry, is_updated_transform):
        mesh = self.id_data
        log("Updating mesh: %s" % mesh.name)

        rpr_mesh = rpr_context.meshes.get(utils.key(mesh), None)
        if rpr_mesh:
            if is_updated_geometry:
                # TODO: recreate mesh
                pass

            if is_updated_transform:
                rpr_mesh.set_transform(utils.get_transform(obj))

        else:
            # TODO: create mesh
            pass

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
