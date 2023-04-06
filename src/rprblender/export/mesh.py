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
import math

import bpy
import bmesh
import mathutils

import pyrpr
from rprblender.engine.context import RPRContext, RPRContext2
from . import object, material, volume
from rprblender.utils import get_data_from_collection, BLENDER_VERSION

from rprblender.utils import logging
log = logging.Log(tag='export.mesh')


NUM_TRIANGLES_WARNING = 1000000


@dataclass(init=False)
class MeshData:
    """ Dataclass which holds all mesh settings. It is used also for area lights creation """

    vertices: np.array
    normals: np.array
    uvs: np.array
    vertex_indices: np.array
    normal_indices: np.array
    uv_indices: np.array
    num_face_vertices: np.array
    vertex_colors: np.array = None
    area: float = None

    @staticmethod
    def init_from_mesh(mesh: bpy.types.Mesh, calc_area=False, obj=None):
        """ Returns MeshData from bpy.types.Mesh """
        uv_mesh = mesh
        if obj and obj.mode != 'OBJECT':
            mesh = obj.data
        # Looks more like Blender's bug that we have to check that mesh has calc_normals_split().
        # It is possible after deleting corresponded object with such mesh from the scene.
        if not hasattr(mesh, 'calc_normals_split'):
            log.warn("No calc_normals_split() in mesh", mesh)
            return None

        # preparing mesh to export
        mesh.calc_normals_split()
        mesh.calc_loop_triangles()

        # getting mesh export data
        tris_len = len(mesh.loop_triangles)
        if tris_len == 0:
            return None

        if tris_len > NUM_TRIANGLES_WARNING:
            log.warn(f'Found object {obj.name_full} with {tris_len:,} triangles. '
                     f'Consider simplifying geometry to less than {NUM_TRIANGLES_WARNING:,} triangles')

        data = MeshData()
        data.vertices = get_data_from_collection(mesh.vertices, 'co', (len(mesh.vertices), 3))
        data.normals = get_data_from_collection(mesh.loop_triangles, 'split_normals',
                                                (tris_len * 3, 3))

        data.uvs = []
        data.uv_indices = []

        if not hasattr(mesh, 'calc_normals_split'):
            log.warn("No calc_normals_split() in mesh", mesh)
            uv_mesh = mesh

        uv_mesh.calc_normals_split()
        uv_mesh.calc_loop_triangles()


        primary_uv = uv_mesh.rpr.primary_uv_layer
        if primary_uv:
            uvs = get_data_from_collection(primary_uv.data, 'uv', (len(primary_uv.data), 2))
            uv_indices = get_data_from_collection(mesh.loop_triangles, 'loops',
                                                  (tris_len * 3,), np.int32)

            if len(uvs) > 0:
                data.uvs.append(uvs)
                data.uv_indices.append(uv_indices)

            if obj:
                secondary_uv = uv_mesh.rpr.secondary_uv_layer(obj)
                if secondary_uv:
                    uvs = get_data_from_collection(secondary_uv.data, 'uv', (len(secondary_uv.data), 2))
                    if len(uvs) > 0:
                        data.uvs.append(uvs)
                        data.uv_indices.append(uv_indices)

        data.num_face_vertices = np.full((tris_len,), 3, dtype=np.int32)
        data.vertex_indices = get_data_from_collection(mesh.loop_triangles, 'vertices',
                                                       (tris_len * 3,), np.int32)
        data.normal_indices = np.arange(tris_len * 3, dtype=np.int32)

        if calc_area:
            data.area = sum(tri.area for tri in mesh.loop_triangles)

        # set active vertex color map
        if mesh.vertex_colors.active:
            color_data = mesh.vertex_colors.active.data
            # getting vertex colors and its indices (the same as uv_indices)
            colors = get_data_from_collection(color_data, 'color', (len(color_data), 4))
            color_indices = data.uv_indices[0] if (data.uv_indices is not None and len(data.uv_indices) > 0) else \
                get_data_from_collection(mesh.loop_triangles, 'loops',
                                         (tris_len * 3,), np.int32)

            # preparing vertex_color buffer with the same size as vertices and
            # setting its data by indices from vertex colors
            if colors[color_indices].size > 0:
                data.vertex_colors = np.zeros((len(data.vertices), 4), dtype=np.float32)
                data.vertex_colors[data.vertex_indices] = colors[color_indices]

        return data

    @staticmethod
    def init_from_shape_type(shape_type, size, size_y, segments):
        """
        Returns MeshData depending of shape_type of area light.
        Possible values of shape_type: 'SQUARE', 'RECTANGLE', 'DISK', 'ELLIPSE'
        """

        bm = bmesh.new()
        try:
            if shape_type in ('SQUARE', 'RECTANGLE'):
                bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)

            elif shape_type in ('DISK', 'ELLIPSE'):
                bmesh.ops.create_circle(bm, cap_ends=True, cap_tris=True, segments=segments, radius=0.5)

            elif shape_type == 'SPHERE':
                if BLENDER_VERSION < '3.0':
                    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=segments, diameter=1.0)

                else:
                    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=segments, radius=0.5)

            elif shape_type == 'CUBE':
                bmesh.ops.create_cube(bm, size=size)

            else:
                raise TypeError("Incorrect shape type", shape_type)

            data = MeshData()

            # getting uvs before modifying mesh
            bm.verts.ensure_lookup_table()
            main_uv_set = np.fromiter(
                (vert.co[i] + 0.5 for vert in bm.verts for i in (0, 1)),
                dtype=np.float32).reshape(-1, 2)
            data.uvs = [main_uv_set]

            # scale and rotate mesh around Y axis
            bmesh.ops.scale(bm, verts=bm.verts,
                            vec=(size, size if shape_type in ('SQUARE', 'DISK', 'SPHERE') else size_y, size))
            bmesh.ops.rotate(bm, verts=bm.verts,
                             matrix=mathutils.Matrix.Rotation(math.pi, 4, 'Y'))

            # preparing mesh to get data
            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            loop_triangles = bm.calc_loop_triangles()
            tris_len = len(loop_triangles)

            data.vertices = np.fromiter(
                (x for vert in bm.verts for x in vert.co),
                dtype=np.float32).reshape(-1, 3)
            data.normals = np.fromiter(
                (x for vert in bm.verts for x in vert.normal),
                dtype=np.float32).reshape(-1, 3)

            data.num_face_vertices = np.full((tris_len,), 3, dtype=np.int32)
            data.vertex_indices = np.fromiter((vert.vert.index for tri in loop_triangles for vert in tri), dtype=np.int32)
            data.normal_indices = data.vertex_indices
            data.uv_indices = [data.vertex_indices]

            data.area = sum(face.calc_area() for face in bm.faces)

            return data

        finally:
            bm.free()


def assign_materials(rpr_context: RPRContext, rpr_shape: pyrpr.Shape, obj: bpy.types.Object,
                     material_override=None) -> bool:
    """
    Assigns materials from material_slots to rpr_shape. It also syncs new material.
    Override material is used instead of mesh-assigned if present.
    """
    # ViewLayer override is used for all objects in scene on that view layer
    if material_override:
        return assign_override_material(rpr_context, rpr_shape, obj, material_override)

    material_slots = obj.material_slots
    if len(material_slots) == 0:
        if rpr_shape.materials:
            rpr_shape.set_material(None)
            return True

        return False

    mesh = obj.data
    material_unique_indices = (0,)
    # mesh here could actually be curve data which wouldn't have loop_triangles
    if len(material_slots) > 1 and getattr(mesh, 'loop_triangles', None):
        # Multiple materials found, going to collect indices of actually used materials
        material_indices = np.fromiter((tri.material_index for tri in mesh.loop_triangles), dtype=np.int32)
        material_unique_indices = np.unique(material_indices)

    # Apply used materials to mesh
    for i in material_unique_indices:
        slot = material_slots[i]

        if not slot.material:
            continue

        log(f"Syncing material '{slot.name}'; {slot}")

        rpr_material = material.sync(rpr_context, slot.material, obj=obj)

        if rpr_material:
            if len(material_unique_indices) == 1:
                rpr_shape.set_material(rpr_material)
            else:
                # It is important not to remove previous unused materials here, because core
                # could crash. They will be in memory till mesh exists.
                face_indices = np.array(np.where(material_indices == i)[0], dtype=np.int32)
                rpr_shape.set_material_faces(rpr_material, face_indices)
        else:
            rpr_shape.set_material(None)

    # sync displacement and volume for shape with its first material
    if material_slots and material_slots[0].material:
        mat = material_slots[0].material

        smoke_modifier = volume.get_smoke_modifier(obj)
        if not smoke_modifier or isinstance(rpr_context, RPRContext2):
            # setting volume material
            rpr_volume = material.sync(rpr_context, mat, 'Volume', obj=obj)
            rpr_shape.set_volume_material(rpr_volume)

        # setting displacement material
        if mat.cycles.displacement_method in {'DISPLACEMENT', 'BOTH'}:
            rpr_displacement = material.sync(rpr_context, mat, 'Displacement', obj=obj)
            rpr_shape.set_displacement_material(rpr_displacement)
            # if no subdivision set that up to 'high' so displacement looks good
            # note subdivision is capped to resolution

            # TODO
            # Turn off this params to avoid memory leak in certain cases.
            # Second, majority of user cases it doesn't take into account at all but should.
            # Verify after this https://amdrender.atlassian.net/browse/RPR-1149
            # PR to apply https://github.com/GPUOpen-LibrariesAndSDKs/RadeonProRenderBlenderAddon/pull/557
            #
            # if rpr_shape.subdivision is None:
            #     rpr_shape.subdivision = {
            #         'level': 10,
            #         'boundary': pyrpr.SUBDIV_BOUNDARY_INTERFOP_TYPE_EDGE_AND_CORNER,
            #         'crease_weight': 10
            #     }

        else:
            rpr_shape.set_displacement_material(None)

    return True


def assign_override_material(rpr_context, rpr_shape, obj, material_override) -> bool:
    """ Apply override material to shape if material is correct """
    rpr_material = material.sync(rpr_context, material_override, obj=obj)
    rpr_displacement = material.sync(rpr_context, material_override, 'Displacement', obj=obj)
    rpr_shape.set_material(rpr_material)
    rpr_shape.set_displacement_material(rpr_displacement)

    return bool(rpr_material or rpr_displacement)


def export_visibility(obj, rpr_shape, indirect_only):
    """ Exports visibility settings """
    if BLENDER_VERSION >= '3.0':
        rpr_shape.set_visibility_primary_only(obj.visible_camera and not indirect_only)
        rpr_shape.set_visibility_ex("visible.reflection", obj.visible_glossy)
        rpr_shape.set_visibility_ex("visible.reflection.glossy", obj.visible_glossy)
        rpr_shape.set_visibility_ex("visible.refraction", obj.visible_transmission)
        rpr_shape.set_visibility_ex("visible.refraction.glossy", obj.visible_transmission)
        rpr_shape.set_visibility_ex("visible.diffuse", obj.visible_diffuse)
        rpr_shape.set_shadow(obj.visible_shadow)

    else:
        visibility = obj.cycles_visibility
        rpr_shape.set_visibility_primary_only(visibility.camera and not indirect_only)
        rpr_shape.set_visibility_ex("visible.reflection", visibility.glossy)
        rpr_shape.set_visibility_ex("visible.reflection.glossy", visibility.glossy)
        rpr_shape.set_visibility_ex("visible.refraction", visibility.transmission)
        rpr_shape.set_visibility_ex("visible.refraction.glossy", visibility.transmission)
        rpr_shape.set_visibility_ex("visible.diffuse", visibility.diffuse)
        rpr_shape.set_shadow(visibility.shadow)

    rpr_shape.set_visibility_ex("visible.receive_shadow", obj.rpr.receive_shadow)
    obj.rpr.set_shadow_color(rpr_shape)
    obj.rpr.set_catchers(rpr_shape)


def sync_visibility(rpr_context, obj: bpy.types.Object, rpr_shape: pyrpr.Shape, indirect_only: bool = False):
    from rprblender.engine.viewport_engine import ViewportEngine

    rpr_shape.set_visibility(
        obj.show_instancer_for_viewport if rpr_context.engine_type == ViewportEngine.TYPE else
        obj.show_instancer_for_render
    )
    if not rpr_shape.is_visible:
        return

    export_visibility(obj, rpr_shape, indirect_only)
    obj.rpr.export_subdivision(rpr_shape)

    rpr_shape.set_contour_ignore(not obj.rpr.visibility_contour)

    if obj.rpr.portal_light:
        # Register mesh as a portal light, set "Environment" light group
        rpr_shape.set_light_group_id(0)
        rpr_shape.set_portal_light(True)
    else:
        # all non-portal light meshes are set to light group 3 for emissive objects
        rpr_shape.set_light_group_id(3)
        rpr_shape.set_portal_light(False)


def sync(rpr_context: RPRContext, obj: bpy.types.Object, **kwargs):
    """ Creates pyrpr.Shape from obj.data:bpy.types.Mesh """

    mesh = kwargs.get("mesh", obj.data)
    material_override = kwargs.get("material_override", None)
    smoke_modifier = volume.get_smoke_modifier(obj)

    indirect_only = kwargs.get("indirect_only", False)
    log("sync", mesh, obj, "IndirectOnly" if indirect_only else "")

    obj_key = object.key(obj)
    transform = object.get_transform(obj)

    # the mesh key is used to find duplicated mesh data
    mesh_key = obj.data.name
    is_potential_instance = len(obj.modifiers) == 0
    
    # if an object has no modifiers it could potentially instance a mesh
    # instead of exporting a new one
    if is_potential_instance and mesh_key in rpr_context.mesh_masters:
        rpr_mesh = rpr_context.mesh_masters[mesh_key]
        rpr_shape = rpr_context.create_instance(obj_key, rpr_mesh)
    else:
        data = MeshData.init_from_mesh(mesh, obj=obj)
        if not data:
            rpr_context.create_empty_object(obj_key)
            return

        deformation_data = rpr_context.deformation_cache.get(obj_key)

        if smoke_modifier and isinstance(rpr_context, RPRContext2):
            transform = volume.get_transform(obj)
            rpr_shape = rpr_context.create_mesh(
                obj_key,
                None, None, None,
                None, None, None,
                None,
                {pyrpr.MESH_VOLUME_FLAG: 1}
            )

        elif deformation_data and np.any(data.vertices != deformation_data.vertices) and \
                np.any(data.normals != deformation_data.normals):
            vertices = np.concatenate((data.vertices, deformation_data.vertices))
            normals = np.concatenate((data.normals, deformation_data.normals))
            rpr_shape = rpr_context.create_mesh(
                obj_key,
                np.ascontiguousarray(vertices), np.ascontiguousarray(normals), data.uvs,
                data.vertex_indices, data.normal_indices, data.uv_indices,
                data.num_face_vertices,
                {pyrpr.MESH_MOTION_DIMENSION: 2}
            )
        else:
            rpr_shape = rpr_context.create_mesh(
                obj_key,
                data.vertices, data.normals, data.uvs,
                data.vertex_indices, data.normal_indices, data.uv_indices,
                data.num_face_vertices
            )

        if data.vertex_colors is not None:
            rpr_shape.set_vertex_colors(data.vertex_colors)

        # add mesh to masters if no modifiers
        if is_potential_instance:
            rpr_context.mesh_masters[mesh_key] = rpr_shape

    # create an instance of the mesh
    rpr_shape.set_name(obj_key)
    rpr_shape.set_id(obj.pass_index)
    rpr_context.set_aov_index_lookup(obj.pass_index, obj.pass_index,
                                     obj.pass_index, obj.pass_index, 1.0)

    

    assign_materials(rpr_context, rpr_shape, obj, material_override)

    rpr_context.scene.attach(rpr_shape)

    rpr_shape.set_transform(transform)
    object.export_motion_blur(rpr_context, obj_key, transform)

    sync_visibility(rpr_context, obj, rpr_shape, indirect_only=indirect_only)


def sync_update(rpr_context: RPRContext, obj: bpy.types.Object, is_updated_geometry, is_updated_transform, **kwargs):
    """ Update existing mesh from obj.data: bpy.types.Mesh or create a new mesh """

    mesh = obj.data
    log("sync_update", obj, mesh)

    obj_key = object.key(obj)
    mesh_key = obj.data.name
    rpr_shape = rpr_context.objects.get(obj_key, None)
    if rpr_shape:
        if is_updated_geometry:
            rpr_context.remove_object(obj_key)
            if mesh_key in rpr_context.mesh_masters:
                rpr_context.mesh_masters.pop(mesh_key)
            sync(rpr_context, obj)
            return True

        if is_updated_transform:
            rpr_shape.set_transform(object.get_transform(obj))

        indirect_only = kwargs.get("indirect_only", False)
        material_override = kwargs.get("material_override", None)
        
        sync_visibility(rpr_context, obj, rpr_shape, indirect_only=indirect_only)
        assign_materials(rpr_context, rpr_shape, obj, material_override)
        return True

    sync(rpr_context, obj, **kwargs)
    return True


def cache_blur_data(rpr_context, obj: bpy.types.Object, mesh=None):
    obj_key = object.key(obj)
    if obj.rpr.motion_blur:
        rpr_context.transform_cache[obj_key] = object.get_transform(obj)

    if obj.rpr.deformation_blur and isinstance(rpr_context, RPRContext2):
        rpr_context.deformation_cache[obj_key] = MeshData.init_from_mesh(mesh if mesh else obj.data)
