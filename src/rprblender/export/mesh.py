from dataclasses import dataclass
import numpy as np
import math

import bpy
import bmesh
import mathutils

import pyrpr
from rprblender.engine.context import RPRContext
from . import object, material, volume

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
    vertex_colors: np.array = None
    area: float = None

    @staticmethod
    def init_from_mesh(mesh: bpy.types.Mesh, calc_area=False):
        """ Returns MeshData from bpy.types.Mesh """

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

        data = MeshData()
        data.vertices = np.fromiter(
            (x for vert in mesh.vertices for x in vert.co),
            dtype=np.float32).reshape(-1, 3)
        data.normals = np.fromiter(
            (x for tri in mesh.loop_triangles for norm in tri.split_normals for x in norm),
            dtype=np.float32).reshape(-1, 3)

        data.uvs = []
        data.uv_indices = []

        primary_uv = mesh.rpr.primary_uv_layer
        if primary_uv:
            uvs = np.fromiter(
                (x for uv_data in primary_uv.data for x in uv_data.uv),
                dtype=np.float32).reshape(-1, 2)
            if len(uvs) > 0:
                uv_indices = np.fromiter((x for tri in mesh.loop_triangles for x in tri.loops),
                                         dtype=np.int32)
                data.uvs.append(uvs)
                data.uv_indices.append(uv_indices)

            secondary_uv = mesh.rpr.secondary_uv_layer
            if secondary_uv:
                uvs = np.fromiter(
                    (x for uv_data in secondary_uv.data for x in uv_data.uv),
                    dtype=np.float32).reshape(-1, 2)
                if len(uvs) > 0:
                    uv_indices = np.fromiter((x for tri in mesh.loop_triangles for x in tri.loops),
                                             dtype=np.int32)
                    data.uvs.append(uvs)
                    data.uv_indices.append(uv_indices)

        data.num_face_vertices = np.full((tris_len,), 3, dtype=np.int32)
        data.vertex_indices = np.fromiter((x for tri in mesh.loop_triangles for x in tri.vertices), dtype=np.int32)
        data.normal_indices = np.arange(tris_len * 3, dtype=np.int32)

        if calc_area:
            data.area = sum(tri.area for tri in mesh.loop_triangles)

        # set active vertex color map
        if mesh.vertex_colors.active:
            color_data = mesh.vertex_colors.active.data

            # getting vertex colors and its indices (the same as uv_indices)
            colors = np.fromiter(
                (x for vert in color_data for x in vert.color),
                dtype=np.float32).reshape(-1, 4)
            color_indices = data.uv_indices if data.uv_indices is not None else \
                np.fromiter((x for tri in mesh.loop_triangles for x in tri.loops), dtype=np.int32)

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

            elif shape_type in ('SPHERE'):
                bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=segments, diameter=1.0)

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
                     material_override=None):
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
        if not smoke_modifier:
            # setting volume material
            rpr_volume = material.sync(rpr_context, mat, 'Volume')
            rpr_shape.set_volume_material(rpr_volume)

        # setting displacement material
        if mat.cycles.displacement_method in {'DISPLACEMENT', 'BOTH'}:
            rpr_displacement = material.sync(rpr_context, mat, 'Displacement')
            rpr_shape.set_displacement_material(rpr_displacement)
        else:
            rpr_shape.set_displacement_material(None)

    return True


def assign_override_material(rpr_context, rpr_shape, obj, material_override):
    """ Apply override material to shape if material is correct """
    rpr_material = material.sync(rpr_context, material_override, obj=obj)
    rpr_displacement = material.sync(rpr_context, material_override, 'Displacement')
    rpr_shape.set_material(rpr_material)
    rpr_shape.set_displacement_material(rpr_displacement)

    return rpr_material or rpr_displacement


def sync_visibility(rpr_context, obj: bpy.types.Object, rpr_shape: pyrpr.Shape, indirect_only: bool = False):
    from rprblender.engine.viewport_engine import ViewportEngine

    rpr_shape.set_visibility(
        obj.show_instancer_for_viewport if rpr_context.engine_type == ViewportEngine.TYPE else
        obj.show_instancer_for_render
    )
    if not rpr_shape.is_visible:
        return

    obj.rpr.export_visibility(rpr_shape, indirect_only)
    obj.rpr.export_subdivision(rpr_shape)

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
    indirect_only = kwargs.get("indirect_only", False)
    log("sync", mesh, obj, "IndirectOnly" if indirect_only else "")

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
    rpr_shape.set_name(obj.name)

    if data.vertex_colors is not None:
        rpr_shape.set_vertex_colors(data.vertex_colors)

    assign_materials(rpr_context, rpr_shape, obj, material_override)

    rpr_context.scene.attach(rpr_shape)
    rpr_shape.set_transform(object.get_transform(obj))

    sync_visibility(rpr_context, obj, rpr_shape, indirect_only=indirect_only)


def sync_update(rpr_context: RPRContext, obj: bpy.types.Object, is_updated_geometry, is_updated_transform, **kwargs):
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

        indirect_only = kwargs.get("indirect_only", False)
        material_override = kwargs.get("material_override", None)

        sync_visibility(rpr_context, obj, rpr_shape, indirect_only=indirect_only)
        assign_materials(rpr_context, rpr_shape, obj, material_override)
        return True

    sync(rpr_context, obj, **kwargs)
    return True
