import numpy as np

import bpy
import bmesh

from . import RPR_Operator


FOG_KEY = 'RPR.Fog'


class RPR_WORLD_OP_create_fog_object(RPR_Operator):
    bl_idname = "rpr.op_create_fog_object"
    bl_label = "Create Fog Object"
    bl_description = "Create 'FOG' object in scene collection"

    def execute(self, context):
        scene = context.scene

        # calculating scene bounding box through all scene objects bounding boxes
        min_pos = np.array((np.Inf, np.Inf, np.Inf))
        max_pos = -min_pos
        is_min_max_set = False
        for o in scene.objects:
            m = np.array(o.matrix_world)
            for p in o.bound_box:
                world_p = m @ (*p, 1.0)
                min_pos = np.minimum(min_pos, world_p[:3])
                max_pos = np.maximum(max_pos, world_p[:3])
                is_min_max_set = True

        if not is_min_max_set:
            max_pos = np.array((10, 10, 10))
            min_pos = -max_pos

        # Creating FOG object
        mesh = bpy.data.meshes.new(FOG_KEY)
        fog_object = bpy.data.objects.new(FOG_KEY, mesh)

        bm = bmesh.new()
        try:
            bmesh.ops.create_cube(bm, size=1.0)
            bm.to_mesh(mesh)
        finally:
            bm.free()

        scene.collection.objects.link(fog_object)
        fog_object.display_type = 'BOUNDS'

        # set position to the center of the scene
        fog_object.location = (min_pos + max_pos) / 2

        # set scale to scene bound box + 10%
        fog_object.scale = (max_pos - min_pos) * 1.1

        # set volume material
        mat = bpy.data.materials.new(name=FOG_KEY)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes

        # Add a diffuse shader and set its location:
        nodes.remove(nodes.get('Principled BSDF'))
        output_node = nodes['Material Output']

        volume_node = nodes.new('ShaderNodeVolumePrincipled')
        volume_node.location = (0, 300)

        # setting default density to 0.01 as more appropriate
        volume_node.inputs['Density'].default_value = 0.01

        mat.node_tree.links.new(output_node.inputs['Volume'], volume_node.outputs['Volume'])

        fog_object.data.materials.append(mat)

        return {'FINISHED'}
