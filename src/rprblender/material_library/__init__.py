import os

import bpy
import io
from xml.etree import ElementTree

from .library import RPRMaterialLibrary
from .loader import RPRXMLMaterialCompiler
from .image_loader import MaterialImageLoader

from rprblender.utils.logging import Log
log = Log(tag="material_library")


# The material library instance, referenced by the material browser properties and material import operator.
rpr_material_library = None


def import_xml_material(material: bpy.types.Material, name: str, xml_path: str, copy_textures: bool):
    """ Create RPR material at current material slot using xml.
    Nodes tree is cleaned if present, new created otherwise.
    New output node added if no output found.
    Change Blender material name to material library name.
    Copy textures locally if requested."""

    def clean_material_tree():
        """ Remove every node from material tree except for output """
        log("Cleaning material nodes tree")
        material.node_tree.nodes.clear()

    def create_material() -> bpy.types.Material:
        """ Create new material and assign to current empty material slot, create slot if none found """
        if not bpy.context.object.material_slots.keys():
            bpy.ops.object.material_slot_add()
        # 2. create material for it
        new_material = bpy.data.materials.new(name=name)
        # 3. assign material to material slot
        bpy.context.object.material_slots[bpy.context.object.active_material_index].material = new_material
        new_material.use_nodes = True

        return new_material

    def create_output_node() -> bpy.types.ShaderNode:
        """ Create and return new output node """
        output_node = material.node_tree.nodes.new('ShaderNodeOutputMaterial')

        log("New output node is {}".format(output_node))
        return output_node

    if not material:
        log("No material tree found, creating new material")
        material = create_material()
    else:
        material.name = name

    # overwrite existing nodes tree
    clean_material_tree()
    output = create_output_node()

    root_folder = rpr_material_library.path
    material_folder = os.path.dirname(xml_path)

    # create images loader
    image_loader = MaterialImageLoader(root_folder, material_folder, copy_textures)

    # create material by xml
    closure = compile_material_from_xml(xml_path, material.node_tree, image_loader)

    # Link closure to output node
    if closure:
        log("Linking closure {} to active output {}".format(closure, output))
        material.node_tree.links.new(closure.outputs[0], output.inputs[0])


def iter_materials(root):
    for material in root.iter(tag='material'):
        material_name = material.get('name')
        yield material_name, {node.get('name'): node for node in material.iter(tag='node')}


def compile_material_from_xml(xml_path: str, node_tree, image_loader):
    if not xml_path or not os.path.isfile(xml_path):
        log.error("Unable to find material xml file '{}'".format(xml_path))
        return None

    # load material xml
    with open(xml_path) as data_file:
        if not data_file:
            log.error("Unable to open material xml file '{}'".format(xml_path))
            return None
        else:
            xml_tree = ElementTree.parse(io.StringIO(data_file.read()))

    materials = [mat for mat in xml_tree.getroot().iter(tag='material')]
    if not materials:
        log.error("Unable to find material in '{}'".format(xml_path))
        return None

    # read first material info
    material_name = materials[0].get('name')

    # Material Library 2.0 uses closure_node to point at output node. For 1.0 use material name.
    closure_name = materials[0].get('closure_node', '')
    nodes = {node.get('name'): node for node in materials[0].iter(tag='node')}

    if closure_name is None:
        # MaterialLibrary 1.0 uses the material name for root node name
        root_node = nodes.get(material_name)
    else:
        # MaterialLibrary 2.0 uses attribute "closure_node" to define at root node
        root_node = nodes.get(closure_name)
    return RPRXMLMaterialCompiler(nodes, node_tree, image_loader).compile(root_node)


def register():
    log('material_browser.register')
    global rpr_material_library
    rpr_material_library = RPRMaterialLibrary()


def unregister():
    log('material_browser.unregister')
    global rpr_material_library
    rpr_material_library.clean_up()
    rpr_material_library = None
