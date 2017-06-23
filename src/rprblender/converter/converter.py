import sys
from rprblender import logging


def log_convert(*args):
    logging.debug(*args, tag='converter')


def error_convert(*args):
    logging.error(*args, tag='converter')


class MaterialConverter:
    offset_y = 40
    minY = 0
    maxY = 0
    offset = 0

    offset_stack = []

    def begin_node_convert(self, cycles_node):
        class Info:
            name = cycles_node.bl_idname
            offset = self.offset_stack[-1].offset if self.offset_stack else 0

        self.offset_stack.append(Info)

    def end_node_convert(self, cycles_node):
        check = self.offset_stack.pop()
        assert check.name == cycles_node.bl_idname

    def cleanup_rpr_materials(self):
        for node in self.tree.nodes:
            name = getattr(node, "bl_idname", None)
            if name and name.startswith('rpr_'):
                log_convert("remove node: ", name)
                self.tree.nodes.remove(node)

    def create_rpr_output_node(self):
        self.output_node = self.material_editor.create_output_node()
        self.begin_node_convert(self.source_output)
        try:
            self.output_node.node.location = self.get_new_loacation(self.source_output)
        finally:
            self.end_node_convert(self.source_output)

    def get_new_loacation(self, node, add_offset=0):
        y = self.minY - (self.maxY - node.location.y)
        assert self.offset_stack
        self.offset_stack[-1].offset += add_offset
        self.last_node_location = node.location[0] - self.offset_stack[-1].offset, y - self.offset_y
        return self.last_node_location

    def calculate_node_graph_bound(self):
        self.minY = sys.float_info.max
        self.maxY = sys.float_info.min
        for node in self.tree.nodes:
            bottom = node.location.y - node.dimensions.y
            if self.minY > bottom:
                self.minY = bottom

            if self.maxY < node.location.y:
                self.maxY = node.location.y
