from dataclasses import dataclass
import numpy as np
import math
from typing import List

import bpy
import bmesh
import mathutils

import pyrpr
from rprblender.engine.context import RPRContext
from . import object, material

from rprblender.utils import logging
log = logging.Log(tag='export.mesh')


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
    area: float = None

    @staticmethod
    def init_from_mesh(mesh: bpy.types.Mesh, calc_area=False):
        """ Returns MeshData from bpy.types.Mesh """

        # preparing mesh to export
        mesh.calc_normals_split()
        mesh.calc_loop_triangles()

        # getting mesh export data
        tris_len = len(mesh.loop_triangles)
        if tris_len == 0:
            return None

        data = MeshData()
        data.vertices = np.fromiter(
            (x for vert in mesh.vertices for x in vert.co), 
            dtype=np.float32).reshape(-1, 3)
        data.normals = np.fromiter(
            (x for tri in mesh.loop_triangles for norm in tri.split_normals for x in norm),
            dtype=np.float32).reshape(-1, 3)

        data.uvs = None
        data.uv_indices = None
        if len(mesh.uv_layers) > 0:
            uv_layer = mesh.uv_layers.active
            uvs = np.fromiter(
                (x for d in uv_layer.data for x in d.uv),
                dtype=np.float32).reshape(-1, 2)
            if len(uvs) > 0:
                data.uvs = uvs
                data.uv_indices = np.fromiter((x for tri in mesh.loop_triangles for x in tri.loops), dtype=np.int32)

        data.num_face_vertices = np.full((tris_len,), 3, dtype=np.int32)
        data.vertex_indices = np.fromiter((x for tri in mesh.loop_triangles for x in tri.vertices), dtype=np.int32)
        data.normal_indices = np.arange(tris_len * 3, dtype=np.int32)

        if calc_area:
            data.area = sum(tri.area for tri in mesh.loop_triangles)

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

            elif shape_type in ('SPHERE'):
                bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=segments, diameter=1.0)

            else:
                raise TypeError("Incorrect shape type", shape_type)

            data = MeshData()

            # getting uvs before modifying mesh
            bm.verts.ensure_lookup_table()
            data.uvs = np.fromiter(
                (vert.co[i] + 0.5 for vert in bm.verts for i in (0, 1)),
                dtype=np.float32).reshape(-1, 2)

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
            data.uv_indices = data.vertex_indices

            data.area = sum(face.calc_area() for face in bm.faces)

            return data

        finally:
            bm.free()


def assign_materials(rpr_context: RPRContext, rpr_shape: pyrpr.Shape,
                     material_slots: List[bpy.types.MaterialSlot], mesh: bpy.types.Mesh):
    """ Assigns materials from material_slots to rpr_shape. It also syncs new material """
    if len(material_slots) == 0:
        return False

    material_unique_indices = (0,)
    if len(material_slots) > 1:
        # Multiple materials found, going to collect indices of actually used materials
        material_indices = np.fromiter((tri.material_index for tri in mesh.loop_triangles), dtype=np.int32)
        material_unique_indices = np.unique(material_indices)

    # Apply used materials to mesh
    for i in material_unique_indices:
        slot = material_slots[i]

        if not slot.material:
            continue

        log("Syncing material '%s'" % slot.name, slot)

        rpr_material = material.sync(rpr_context, slot.material)

        if rpr_material:
            if len(material_unique_indices) == 1:
                rpr_shape.set_material(rpr_material)
            else:
                # It is important not to remove previous unused materials here, because core could crash.
                # They will be in memory till mesh exists.
                face_indices = np.array(np.where(material_indices == i)[0], dtype=np.int32)
                rpr_shape.set_material_faces(rpr_material, face_indices)
        else:
            rpr_shape.set_material(None)

    # sync displacement for single material shape only
    if len(material_slots) == 1 and material_slots[0].material:
        rpr_displacement = material.sync(rpr_context, material_slots[0].material, 'Displacement')
        rpr_shape.set_displacement_material(rpr_displacement)
    else:
        rpr_shape.set_displacement_material(None)

    return True


def sync(rpr_context: RPRContext, obj: bpy.types.Object, mesh: bpy.types.Mesh = None):
    """ Creates pyrpr.Shape from obj.data:bpy.types.Mesh """

    if not mesh:
        mesh = obj.data

    log("sync", mesh, obj)

    obj_key = object.key(obj)
    data = MeshData.init_from_mesh(mesh)
    if not data:
        rpr_context.create_empty_object(obj_key)
        return

    rpr_shape = rpr_context.create_mesh(
        obj_key,
        data.vertices, data.normals, data.uvs,
        data.vertex_indices, data.normal_indices, data.uv_indices,
        data.num_face_vertices
    )
    rpr_shape.set_name(f"{obj.name}:{mesh.name}")

    assign_materials(rpr_context, rpr_shape, obj.material_slots, mesh)

    rpr_context.scene.attach(rpr_shape)
    rpr_shape.set_transform(object.get_transform(obj))
    obj.rpr.export_visibility(rpr_shape)
    obj.rpr.export_subdivision(rpr_shape)

    # if this is an hidden instances emitter
    if not obj.show_instancer_for_render:
        rpr_shape.set_visibility(False)

    if obj.rpr.portal_light:
        # Register mesh as a portal light, set "Environment" light group
        rpr_shape.set_light_group_id(0)
        rpr_shape.set_portal_light(True)
    else:
        # all non-portal light meshes are set to light group 3 for emissive objects
        rpr_shape.set_light_group_id(3)
        rpr_shape.set_portal_light(False)


def sync_update(rpr_context: RPRContext, obj: bpy.types.Object, is_updated_geometry, is_updated_transform):
    """ Update existing mesh from obj.data: bpy.types.Mesh or create a new mesh """

    mesh = obj.data
    log("sync_update", obj, mesh)

    obj_key = object.key(obj)
    rpr_shape = rpr_context.objects.get(obj_key, None)
    if rpr_shape:
        if is_updated_geometry:
            rpr_context.remove_object(obj_key)
            sync(rpr_context, obj)
            return True

        if is_updated_transform:
            rpr_shape.set_transform(object.get_transform(obj))
            return True

        updated = assign_materials(rpr_context, rpr_shape, obj.material_slots, mesh)
        return updated

    sync(rpr_context, obj)
    return True
