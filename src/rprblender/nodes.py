import bpy
import nodeitems_utils
from nodeitems_utils import NodeCategory, NodeItem, NodeItemCustom
import random
import sys
import rprblender.node_editor

from . import rpraddon
from . import logging

RPR_SHADER_TREE_NAME = 'RPRTreeType'
RPR_NODE_GROUP_PREFIX = 'RPRGroupName_'


@rpraddon.register_class
class RPRMaterialNodeTree(bpy.types.ShaderNodeTree):
    bl_idname = RPR_SHADER_TREE_NAME
    bl_label = 'RPR Material Nodes'
    bl_icon = 'MATERIAL'

    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == 'RPR'

    @classmethod
    def get_from_context(cls, context):
        obj = context.active_object
        if obj:
            material = obj.active_material
            if material:
                return material.node_tree, material, material

        return None, None, None


class RPRTreeNode(bpy.types.ShaderNode):
    bl_width_min = 160
    has_thumbnail = False

    def get_thumbnail_enum(self, context):
        if self.has_thumbnail:
            thumbnail = self.get_thumbnail()
            if not thumbnail:
                return []
            thumbnail.initialize(self)
            return [("thumbnail", "thumbnail", '', thumbnail.get_preview().icon_id, 0)]

    @classmethod
    def poll(cls, tree):
        return tree.bl_idname == RPR_SHADER_TREE_NAME or tree.bl_idname == 'ShaderNodeTree' and bpy.context.scene.render.engine == 'RPR'

    def update(self):
        scene = bpy.context.scene
        mat = scene.objects.active.active_material
        if mat and mat.node_tree:
            mat.node_tree.update_tag()

    def get_thumbnail(self):
        return get_node_thumbnail(self)

    def draw_thumbnail(self, layout):
        if bpy.context.scene.rpr.thumbnails.enable:
            sub = layout.row()
            sub.alignment = "RIGHT"
            size = 1.2 if bpy.context.scene.rpr.thumbnails.use_large_preview else 0.6
            sub.scale_x = size
            sub.scale_y = size
            sub.template_icon_view(self, "thumbnail", False, 8)

    def redraw(self):
        for window in bpy.context.window_manager.windows:
            screen = window.screen
            for area in screen.areas:
                if area.type == 'NODE_EDITOR':
                    area.tag_redraw()


class RPRNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, tree):
        return tree.space_data.tree_type == RPR_SHADER_TREE_NAME


class RPRPanel:
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    COMPAT_ENGINES = {'RPR'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return rd.engine in cls.COMPAT_ENGINES


########################################################################################################################

@rpraddon.register_class
class RPRNodeGroupData(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.ShaderNodeTree.rpr_data = bpy.props.PointerProperty(
            name="RPR Data",
            type=cls,
        )
        cls.group_name_id = bpy.props.StringProperty(
            name='Group Tree Id',
            default='',
        )

    @classmethod
    def unregister(cls):
        del bpy.types.ShaderNodeTree.rpr_data


class RPRGroupNode(RPRTreeNode):
    bl_icon = 'OUTLINER_OB_EMPTY'
    bl_width_min = 180

    @classmethod
    def poll(cls, context):
        return bpy.context.scene.render.engine == 'RPR'

    def draw_buttons(self, context, layout):
        ng = get_node_groups_by_id(self.bl_idname)
        if ng:
            layout.prop(ng, 'name')
        layout.operator('rpr.node_group_edit', text='Edit')

    def init(self, context):
        tree = get_node_groups_by_id(self.bl_idname)
        if not tree:
            return

        input_template = generate_inputs(tree)
        for socket_name, socket_bl_idname in input_template:
            s = self.inputs.new(socket_bl_idname, socket_name)

        output_template = generate_outputs(tree)
        for socket_name, socket_bl_idname in output_template:
            self.outputs.new(socket_bl_idname, socket_name)


def is_rpr_node_group(ng):
    return hasattr(ng, 'rpr_data') and ng.rpr_data.group_name_id != ''


def is_node_group_id(ng, name):
    return is_rpr_node_group(ng) and ng.rpr_data.group_name_id == name


def get_node_groups_by_id(name):
    if not name.startswith(RPR_NODE_GROUP_PREFIX):
        return None
    trees = [ng for ng in bpy.data.node_groups if is_node_group_id(ng, name)]
    return trees[0] if len(trees) else None


def group_make():
    tree = bpy.data.node_groups.new('RPR Node Group', 'ShaderNodeTree')
    tree.use_fake_user = True
    nodes = tree.nodes

    node_input = nodes.new('rpr_shader_node_group_input')
    node_input.location = (-300, 0)
    node_input.selected = False

    node_output = nodes.new('rpr_shader_node_group_output')
    node_output.location = (300, 0)
    node_output.selected = False

    logging.info('New group was made.')
    return tree


def get_other_socket(socket):
    if not socket.is_linked:
        return None
    if not socket.is_output:
        other = socket.links[0].from_socket
    else:
        other = socket.links[0].to_socket

    if other.node.bl_idname == 'NodeReroute':
        if not socket.is_output:
            return get_other_socket(other.node.inputs[0])
        else:
            return get_other_socket(other.node.outputs[0])
    else:
        return other


def get_socket_data(socket):
    other = get_other_socket(socket)
    if socket.bl_idname == "rpr_dummy_socket":
        socket = get_other_socket(socket)

    socket_bl_idname = socket.bl_idname
    socket_name = socket.name
    return socket_name, socket_bl_idname


def generate_inputs(tree):
    in_socket = []
    input_node = tree.nodes.get("Group Inputs")
    if input_node:
        for idx, socket in enumerate(input_node.outputs):
            if socket.is_linked:
                socket_name, socket_bl_idname = get_socket_data(socket)
                data = [socket_name, socket_bl_idname]
                in_socket.append(data)
    return in_socket


def generate_outputs(tree):
    out_socket = []
    output_node = tree.nodes.get("Group Outputs")
    if output_node:
        for socket in output_node.inputs:
            if socket.is_linked:
                socket_name, socket_bl_idname = get_socket_data(socket)
                out_socket.append((socket_name, socket_bl_idname))
    return out_socket


def node_groups_load_post():
    node_groups = [ng for ng in bpy.data.node_groups if is_rpr_node_group(ng)]
    for ng in node_groups:
        update_cls(ng)


def socket_index(socket):
    node = socket.node
    sockets = node.outputs if socket.is_output else node.inputs
    for i, s in enumerate(sockets):
        if s == socket:
            return i


def replace_socket(socket, new_type, new_name=None, new_pos=None):
    socket_name = new_name or socket.name
    socket_pos = new_pos or socket_index(socket)
    ng = socket.id_data

    if socket.is_output:
        outputs = socket.node.outputs
        to_sockets = [l.to_socket for l in socket.links]

        outputs.remove(socket)
        new_socket = outputs.new(new_type, socket_name)
        outputs.move(len(outputs) - 1, socket_pos)

        for to_socket in to_sockets:
            ng.links.new(new_socket, to_socket)

    else:
        inputs = socket.node.inputs
        from_socket = socket.links[0].from_socket if socket.is_linked else None

        inputs.remove(socket)
        new_socket = inputs.new(new_type, socket_name)
        inputs.move(len(inputs) - 1, socket_pos)

        if from_socket:
            ng.links.new(from_socket, new_socket)

    return new_socket


def instances(tree):
    res = []
    all_trees = [ng for ng in bpy.data.node_groups if is_rpr_node_group(ng) and ng.nodes]

    for material in bpy.data.materials:
        t = material.node_tree
        if not t or not t.nodes:
            continue
        all_trees.append(t)

    for t in all_trees:
        for node in t.nodes:
            if is_node_group_id(tree, node.bl_idname):
                res.append(node)

    return res


map_lookup = {'outputs': 'inputs', 'inputs': 'outputs'}


class RPRNodeSocketConnectorHelper:
    socket_map = {'outputs': 'to_socket', 'inputs': 'from_socket'}
    node_kind = bpy.props.StringProperty()

    def update(self):
        kind = self.node_kind
        if not kind:
            return

        tree = self.id_data
        if tree.bl_idname != 'ShaderNodeTree':
            return

        socket_list = getattr(self, kind)

        if len(socket_list) == 0:
            logging.info('Skip update')
            return

        if socket_list[-1].is_linked:
            socket = socket_list[-1]
            cls = update_cls(tree)
            if kind == "outputs":
                new_name, new_type = cls.input_template[-1]
            else:
                new_name, new_type = cls.output_template[-1]

            new_socket = replace_socket(socket, new_type, new_name=new_name)

            # update instances
            for instance in instances(tree):
                sockets = getattr(instance, map_lookup[kind])
                new_socket = sockets.new(new_type, new_name)

            socket_list.new('rpr_dummy_socket', '')


def update_cls(tree):
    cls_name = tree.rpr_data.group_name_id

    class C(RPRGroupNode):
        bl_idname = cls_name
        bl_label = 'RPR Group'
        input_template = generate_inputs(tree)
        output_template = generate_outputs(tree)

    C.__name__ = cls_name

    old_cls_ref = getattr(bpy.types, cls_name, None)
    if old_cls_ref:
        bpy.utils.unregister_class(old_cls_ref)
    bpy.utils.register_class(C)
    return C


def get_io_node_locations(nodes):
    offset = 220
    xs = [node.location[0] for node in nodes]
    ys = [node.location[1] for node in nodes]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    y = (min_y + max_y) * 0.5
    return (min_x - offset, y), (max_x + offset, y)


def get_average_location(nodes):
    x, y = 0, 0
    for node in nodes:
        x += node.location[0]
        y += node.location[1]
    d = 1.0 / len(nodes)
    return x * d, y * d


def get_selected_node_by_idname(tree, name):
    for node in tree.nodes:
        if not node.select:
            continue
        if node.bl_idname == name:
            return node
    return None


########################################################################################################################
keymaps_holder = []


def keymap_release():
    for km, kmi in keymaps_holder:
        try:
            km.keymap_items.remove(kmi)
        except Exception as e:
            logging.info("Can't remove key: ", kmi)
        keymaps_holder.clear()


def keymap_init():
    wm = bpy.context.window_manager
    if wm.keyconfigs.addon:
        km = wm.keyconfigs.addon.keymaps.new(name='Node Editor', space_type='NODE_EDITOR')
        # ctrl + G
        kmi = km.keymap_items.new('rpr.node_group_make', 'G', 'PRESS', ctrl=True)
        keymaps_holder.append((km, kmi))
        # alt + G
        kmi = km.keymap_items.new('rpr.node_group_ungroup', 'G', 'PRESS', alt=True)
        keymaps_holder.append((km, kmi))
        # TAB
        kmi = km.keymap_items.new('rpr.node_group_switch', 'TAB', 'PRESS')
        keymaps_holder.append((km, kmi))


########################################################################################################################
# create automatically links nodes
def keys_sort(link):
    return (socket_index(link.to_socket), link.from_node.location.y)


def get_links(tree):
    input_links = sorted([l for l in tree.links if (not l.from_node.select) and (l.to_node.select)], key=keys_sort)
    output_links = sorted([l for l in tree.links if (l.from_node.select) and (not l.to_node.select)], key=keys_sort)
    return dict(input=input_links, output=output_links)


def link_tree(tree, links):
    nodes = tree.nodes
    input_node = nodes.get("Group Inputs")
    output_node = nodes.get("Group Outputs")
    relink_in = []
    relink_out = []
    inputs_remap = {}

    for index, l in enumerate(links['input']):
        i = socket_index(l.to_socket)
        socket = nodes[l.to_node.name].inputs[i]
        if l.from_socket in inputs_remap:
            out_index = inputs_remap[l.from_socket]
            from_socket = input_node.outputs[out_index]
            tree.links.new(from_socket, socket)
        else:
            inputs_remap[l.from_socket] = len(input_node.outputs) - 1
            tree.links.new(input_node.outputs[-1], socket)

        relink_in.append((l.from_socket, inputs_remap[l.from_socket]))

    for index, l in enumerate(links['output']):
        i = socket_index(l.from_socket)
        socket = nodes[l.from_node.name].outputs[i]
        tree.links.new(socket, output_node.inputs[-1])

        relink_out.append((index, l.to_node.name, socket_index(l.to_socket)))

    return relink_in, relink_out


def link_tree_instance(node, relinks):
    tree = node.id_data
    input_relink, output_relink = relinks
    for socket, index in input_relink:
        tree.links.new(socket, node.inputs[index])
    for index, name, socket_index in output_relink:
        tree.links.new(node.outputs[index], tree.nodes[name].inputs[socket_index])


########################################################################################################################
@rpraddon.register_class
class OpGroupEdit(bpy.types.Operator):
    bl_idname = "rpr.node_group_edit"
    bl_label = "Edit Node Group"

    from_shortcut = bpy.props.BoolProperty()


    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == 'RPR'

    def execute(self, context):
        ng = bpy.data.node_groups
        node = context.active_node if self.from_shortcut else context.node
        parent_tree = node.id_data
        group_tree = get_node_groups_by_id(node.bl_idname)

        path = context.space_data.path
        space_data = context.space_data
        if len(path) == 1:
            path.start(parent_tree)
            path.append(group_tree, node=node)
        else:
            path.append(group_tree, node=node)

        return {"FINISHED"}


@rpraddon.register_class
class OpGroupMake(bpy.types.Operator):
    bl_idname = "rpr.node_group_make"
    bl_label = "Makes Node Group"

    @classmethod
    def poll(cls, context):
        if context.scene.render.engine != 'RPR':
            return False
        return context.space_data.tree_type == RPR_SHADER_TREE_NAME

    def execute(self, context):
        tree = context.space_data.edit_tree
        for node in tree.nodes:
            if node.bl_idname == 'rpr_shader_node_group_input' or node.bl_idname == 'rpr_shader_node_group_output':
                node.select = False

        nodes = [node for node in tree.nodes if node.select]
        if not nodes:
            self.report({"WARNING"}, "No nodes selected")
            return {'CANCELLED'}

        bpy.ops.node.clipboard_copy()
        all_links = get_links(tree)
        group = group_make()

        # generate unique name
        cls_name = RPR_NODE_GROUP_PREFIX + str(id(group) ^ random.randint(0, 4294967296))
        group.rpr_data.group_name_id = cls_name

        path = context.space_data.path
        path.append(group)

        bpy.ops.node.clipboard_paste()

        # calculate position for input & output nodes
        input_location, output_loc = get_io_node_locations(nodes)

        input_node = group.nodes.get("Group Inputs")
        input_node.location = input_location
        output_node = group.nodes.get("Group Outputs")
        output_node.location = output_loc

        relinks = link_tree(group, all_links)

        # create class & register
        cls_ref = update_cls(group)
        parent_node = tree.nodes.new(cls_ref.bl_idname)
        parent_node.select = False
        parent_node.location = get_average_location(nodes)

        for node in nodes:
            tree.nodes.remove(node)

        link_tree_instance(parent_node, relinks)
        path.pop()
        path.append(group, node=parent_node)
        bpy.ops.node.view_all()
        return {"FINISHED"}


@rpraddon.register_class
class OpGroupUngroup(bpy.types.Operator):
    bl_idname = "rpr.node_group_ungroup"
    bl_label = "Ungroup"

    @classmethod
    def poll(cls, context):
        if context.scene.render.engine != 'RPR':
            return False
        group_node = context.active_node
        if not group_node:
            return False
        return get_node_groups_by_id(group_node.bl_idname) != None

    def execute(self, context):
        group_node = context.active_node

        # copy data
        bpy.ops.node.select_all(action='DESELECT')
        tree = get_node_groups_by_id(group_node.bl_idname)
        if not tree:
            logging.warn("can't get tree: " , group_node.bl_idname)
            return {'CANCELLED'}
        path = context.space_data.path
        path.append(tree)
        bpy.ops.node.select_all(action='SELECT')
        bpy.ops.node.clipboard_copy()
        path.pop()
        bpy.ops.node.clipboard_paste()

        current_tree = context.space_data.edit_tree
        input_node = get_selected_node_by_idname(current_tree, 'rpr_shader_node_group_input')
        output_node = get_selected_node_by_idname(current_tree, 'rpr_shader_node_group_output')
        if not input_node or not output_node:
            logging.warn("can't get io nodes (%s, %s)" % (input_node, output_node))
            return {'CANCELLED'}

        bpy.ops.node.select_all(action='DESELECT')

        # relink input sockets
        for socket, in_socket in zip(group_node.inputs, input_node.outputs):
            if in_socket.is_linked and socket.is_linked:
                from_socket = socket.links[0].from_socket
                for link in in_socket.links:
                    current_tree.links.new(from_socket, link.to_socket)

        # relink output sockets
        for out_socket, socket in zip(output_node.inputs, group_node.outputs):
            if out_socket.is_linked and socket.is_linked:
                from_socket = out_socket.links[0].from_socket
                for link in socket.links:
                    current_tree.links.new(from_socket, link.to_socket)

        for node in (group_node, input_node, output_node):
            current_tree.nodes.remove(node)

        return {"FINISHED"}


@rpraddon.register_class
class OpTreePathParent(bpy.types.Operator):
    bl_idname = "rpr.node_tree_path_parent"
    bl_label = "Parent Node Tree"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if space.type == 'NODE_EDITOR':
            if len(space.path) > 1:
                if space.edit_tree.bl_idname == "ShaderNodeTree":
                    return True
        return False

    def execute(self, context):
        space = context.space_data
        space.path.pop()
        return {'FINISHED'}


@rpraddon.register_class
class OpNodeGroupSwitch(bpy.types.Operator):
    bl_idname = "rpr.node_group_switch"
    bl_label = "Exit or Enter a node group"

    @classmethod
    def poll(cls, context):
        if context.scene.render.engine != 'RPR':
            return False
        return context.space_data.tree_type == RPR_SHADER_TREE_NAME

    def execute(self, context):
        tree_type = context.space_data.tree_type
        node = context.active_node
        if node:
            if get_node_groups_by_id(node.bl_idname):
                bpy.ops.rpr.node_group_edit(from_shortcut=True)
                return {'FINISHED'}
            else:
                if len(context.space_data.path) > 1:
                    bpy.ops.rpr.node_tree_path_parent()
                    return {'FINISHED'}
        return {'CANCELLED'}


########################################################################################################################

# Socket UI editor
@rpraddon.register_class
class OpNodeSocketMove(bpy.types.Operator):
    bl_idname = "rpr.node_socket_move"
    bl_label = "Move Socket"

    type = bpy.props.EnumProperty(
        items=(('up', '', ''),
               ('down', '', ''),
               ('remove', '', ''),
               ),
    )
    pos = bpy.props.IntProperty()
    node_name = bpy.props.StringProperty()

    def execute(self, context):
        node = context.space_data.edit_tree.nodes[self.node_name]
        tree = node.id_data
        kind = node.node_kind
        io = getattr(node, kind)
        socket = io[self.pos]

        if self.type == 'remove':
            io.remove(socket)
            # update instances
            for instance in instances(tree):
                sockets = getattr(instance, map_lookup[kind])
                sockets.remove(sockets[self.pos])
        else:
            step = -1 if self.type == 'up' else 1
            count = len(io) - 1

            def calc_new_position(pos, step, count):
                return max(0, min(pos + step, count - 1))

            new_pos = calc_new_position(self.pos, step, count)
            io.move(self.pos, new_pos)
            # update instances
            for instance in instances(tree):
                sockets = getattr(instance, map_lookup[kind])
                new_pos = calc_new_position(self.pos, step, len(sockets))
                sockets.move(self.pos, new_pos)

        update_cls(tree)
        return {"FINISHED"}


@rpraddon.register_class
class RPRInOutGroupEditor(RPRPanel, bpy.types.Panel):
    bl_label = "RPR In/Out Group Editor"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        tree = context.space_data.edit_tree
        if not tree:
            return False
        return tree.bl_idname == RPR_SHADER_TREE_NAME or tree.bl_idname == 'ShaderNodeTree' \
                and context.space_data.tree_type == 'RPRTreeType' and is_rpr_node_group(tree)

    def draw(self, context):
        tree = context.space_data.edit_tree
        input_node = tree.nodes.get("Group Inputs")
        output_node = tree.nodes.get("Group Outputs")

        if not (input_node and output_node):
            return

        layout = self.layout
        row = layout.row()
        if context.region.width > 340:
            row = layout.row()
            split = row.split(percentage=0.5)
            col1 = split.box().column()
            split = split.split()
            col2 = split.box().column()
        else:
            col1 = layout.row().box().column()
            layout.separator()
            col2 = layout.row().box().column()

        def set_attrs(cls, **kwargs):
            for name, value in kwargs.items():
                setattr(cls, name, value)

        def draw_socket(col, socket, index):
            if socket.bl_idname == 'rpr_dummy_socket':
                return
            params = dict(node_name=socket.node.name, pos=index)

            row = col.row(align=True)
            row.template_node_socket(color=(0.35, 0.5, 0.8, 1.0))
            row.label(socket.name)

            op = row.operator('rpr.node_socket_move', icon='TRIA_UP', text='')
            set_attrs(op, type='up', **params)
            op = row.operator('rpr.node_socket_move', icon='TRIA_DOWN', text='')
            set_attrs(op, type='down', **params)
            op = row.operator('rpr.node_socket_move', icon='X', text='')
            set_attrs(op, type='remove', **params)

        col1.label('Inputs:')
        for i, socket in enumerate(input_node.outputs):
            draw_socket(col1, socket, i)

        col2.label('Outputs:')
        for i, socket in enumerate(output_node.inputs):
            draw_socket(col2, socket, i)


########################################################################################################################
def group_tools_draw(self, layout, context):
    layout.operator("rpr.node_group_make")
    layout.operator("rpr.node_group_ungroup")
    layout.separator()


def node_group_items(context):
    if context is None:
        return
    space = context.space_data
    if not space:
        return

    tree = space.edit_tree
    if not tree:
        return

    yield NodeItemCustom(draw=group_tools_draw)

    def contains_group(nodetree, group):
        if nodetree == group:
            return True

        for node in nodetree.nodes:
            found = get_node_groups_by_id(node.bl_idname)
            if found and contains_group(found, group):
                return True

        return False

    for ng in context.blend_data.node_groups:
        if not is_rpr_node_group(ng) or contains_group(ng, tree):
            continue
        yield NodeItem(ng.rpr_data.group_name_id, ng.name)


########################################################################################################################
# Category nodes list
########################################################################################################################
node_categories = [
    RPRNodeCategory("RPR_GROUP", "Group", items=node_group_items),

    RPRNodeCategory("RPR_LAYOUT", "Layout", items=[
        NodeItem("NodeFrame"),
        NodeItem("NodeReroute"),
    ]),

    RPRNodeCategory("RPR_OUTPUT", "Output", items=[
        NodeItem("rpr_shader_node_output"),
    ]),
    RPRNodeCategory("RPR_INPUT", "Input", items=[
        NodeItem("rpr_input_node_constant"),
        NodeItem("rpr_input_node_value"),
        NodeItem("rpr_input_node_normalmap"),
        NodeItem("rpr_input_node_bumpmap"),
        NodeItem("rpr_input_node_lookup"),
    ]),

    RPRNodeCategory("RPR_ARITHMETICS", "Arithmetics", items=[
        NodeItem("rpr_arithmetics_node_value_blend"),
        NodeItem("rpr_arithmetics_node_math"),
    ]),

    RPRNodeCategory("RPR_TEXTURE", "Texture", items=[
        NodeItem("rpr_texture_node_image_map"),
        NodeItem("rpr_texture_node_noise2d"),
        NodeItem("rpr_texture_node_gradient"),
        NodeItem("rpr_texture_node_checker"),
        NodeItem("rpr_texture_node_dot"),
    ]),

    RPRNodeCategory("RPR_MAPPING", "Mapping", items=[
        NodeItem("rpr_mapping_node"),
    ]),

    RPRNodeCategory("RPR_FRESNEL", "Fresnel", items=[
        NodeItem("rpr_fresnel_node"),
        NodeItem("rpr_fresnel_schlick_node"),
    ]),

    RPRNodeCategory("RPR_SHADER", "Shader", items=[
        NodeItem("rpr_shader_node_diffuse"),
        NodeItem("rpr_shader_node_emissive"),
        NodeItem("rpr_shader_node_microfacet"),
        NodeItem("rpr_shader_node_microfacet_refraction"),
        NodeItem("rpr_shader_node_blend"),
        NodeItem("rpr_shader_node_diffuse_refraction"),
        NodeItem("rpr_shader_node_oren_nayar"),
        NodeItem("rpr_shader_node_refraction"),
        NodeItem("rpr_shader_node_reflection"),
        NodeItem("rpr_shader_node_transparent"),
        NodeItem("rpr_shader_node_ward"),
        NodeItem("rpr_shader_node_uber"),
        NodeItem("rpr_shader_node_uber2"),
        NodeItem("rpr_shader_node_subsurface"),
        NodeItem("rpr_shader_node_volume"),
        NodeItem("rpr_shader_node_displacement"),
    ]),

]

# import thumbnail after module was defined(it depends on it)
from .node_thumbnail import get_node_thumbnail


def register():
    logging.debug("nodes.register()")
    nodeitems_utils.register_node_categories("RPR_NODES", node_categories)

    keymap_init()


def unregister():
    logging.debug("nodes.unregister()")
    nodeitems_utils.unregister_node_categories("RPR_NODES")

    keymap_release()
