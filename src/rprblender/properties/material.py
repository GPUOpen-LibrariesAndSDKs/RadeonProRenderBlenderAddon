import sys
import traceback

import bpy

import pyrpr
import pyrprx
from rprblender.nodes import export
from rprblender import utils
from rprblender.utils import logging
from rprblender.utils import material as mat_utils
from . import RPR_Properties


log = logging.Log(tag='Material')


class RPR_MaterialParser(RPR_Properties):
    def sync(self, rpr_context) -> pyrprx.Material:
        mat = self.id_data
        mat_key = utils.key(mat)
        log("Syncing material: %s" % mat.name)
        tree = getattr(mat, 'node_tree', None)

        try:
            if not tree:
                raise export.MaterialError("No material tree found for material {}".format(mat))

            # Look for output node
            node = mat_utils.find_rpr_output_node(tree)
            if not node:
                node = mat_utils.find_cycles_output_node(tree)
            if not node:
                raise export.MaterialError("No valid output node found!")

            material = self.parse_cycles_output_node(mat_key, rpr_context, node)
            return material
        except export.MaterialError as e:
            log("MaterialError {}".format(str(e)))
            # traceback.print_exc()
            return export.create_fake_material(mat_key, rpr_context, (1.0, 0.0, 1.0, 1.0))

    @staticmethod
    def get_socket(node, name=None, index=None):
        if name:
            try:
                socket = node.inputs[name]
            except KeyError:
                return None
        elif index:
            try:
                socket = node.inputs[index]
            except IndexError:
                return None
        else:
            return None

        log.debug("get_socket({}, {}, {}): {}; linked {}; links number {}".format
                  (node, name, index, socket, socket.is_linked, len(socket.links)))
        if socket.is_linked and len(socket.links) > 0:
            return socket.links[0].from_socket
        return None

    def parse_cycles_output_node(self, mat_key, rpr_context, node):
        input = self.get_socket(node, name='Surface')  # 'Surface'
        if not input:
            raise export.MaterialError("No input")

        log("Material Output input['Surface'] linked to {}".format(input))
        input_node = input.node
        # log("syncing {}".format(input_node))
        # TODO replace with conversion "Cycles -> RPR" table
        material = export.export_blender_node(rpr_context, input_node)
        if not material:
            raise export.MaterialError("Unable to parse output node {}".format(node))

        return material

    @classmethod
    def register(cls):
        log("Material: Register")
        bpy.types.Material.rpr = bpy.props.PointerProperty(
            name="RPR Material Settings",
            description="RPR material settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        log("Material: Unregister")
        del bpy.types.Material.rpr

