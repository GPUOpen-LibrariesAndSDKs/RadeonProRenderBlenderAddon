import bpy
import numpy as np

from rprblender import utils
from rprblender.utils import logging
from . import RPR_Properties


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

            # preparing mesh to export
            mesh.calc_normals_split()
            mesh.calc_loop_triangles()

            # getting mesh export data
            tris_len = len(mesh.loop_triangles)
            if tris_len == 0:
                return None

            vertices = np.array([vert.co for vert in mesh.vertices], dtype=np.float32)
            normals = np.array([norm for tri in mesh.loop_triangles
                                  for norm in tri.split_normals], dtype=np.float32)

            uvs = None
            uv_indices = None
            if len(mesh.uv_layers) > 0:
                uv_layer = mesh.uv_layers.active
                uvs = np.array([[d.uv.x, d.uv.y] for d in uv_layer.data], dtype=np.float32)
                uv_indices = np.array([tri.loops for tri in mesh.loop_triangles], dtype=np.int32).reshape(
                    (tris_len * 3,))

            num_face_vertices = np.full((tris_len,), 3, dtype=np.int32)
            vertex_indices = np.array([tri.vertices for tri in mesh.loop_triangles], dtype=np.int32).reshape((tris_len*3,))
            normal_indices = np.arange(tris_len*3, dtype=np.int32)

            # creating RPR mesh
            rpr_shape = rpr_context.create_mesh(utils.key(mesh),
                                               vertices, normals, uvs,
                                               vertex_indices, normal_indices, uv_indices,
                                               num_face_vertices)
            rpr_shape.set_name(mesh.name)

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
