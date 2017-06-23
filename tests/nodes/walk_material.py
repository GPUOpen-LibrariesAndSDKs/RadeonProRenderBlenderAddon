import bpy

material = bpy.context.object.active_material
print('hello!', material.node_tree)
nodes = material.node_tree.nodes
for node in nodes:
    print(node, node.bl_idname)
    print([(s.name, type(getattr(s, 'default_value', None)) if not s.is_linked else [l.from_node for l in s.links]) for s in node.inputs])

    if 'ShaderNodeTexImage' == node.bl_idname:
        print(node.image)

#sys.stdout.flush()