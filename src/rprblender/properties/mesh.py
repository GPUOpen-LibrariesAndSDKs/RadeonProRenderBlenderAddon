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

        existing_rpr_mesh = rpr_context.meshes.get(utils.key(mesh), None)
        if existing_rpr_mesh:
            instance_name = "%s/%s" % (mesh.name, obj.name)
            log("Syncing instance: %s" % instance_name)

            rpr_shape = rpr_context.create_instance(utils.key(obj_instance), existing_rpr_mesh)
            rpr_shape.set_name(instance_name)

        else:
            log("Syncing mesh: %s" % mesh.name)
            mesh_prop = mesh_ut.get_mesh_properties(mesh)
            rpr_shape = rpr_context.create_mesh(
                utils.key(mesh),
                mesh_prop['vertices'], mesh_prop['normals'], mesh_prop['uvs'],
                mesh_prop['vertex_indices'], mesh_prop['normal_indices'], mesh_prop['uv_indices'],
                mesh_prop['num_face_vertices']
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
