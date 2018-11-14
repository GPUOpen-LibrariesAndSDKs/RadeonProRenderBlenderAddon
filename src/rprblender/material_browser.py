import platform
import os.path
import json
from pathlib import Path
import shutil

import bpy
import bpy.utils.previews
from bpy.types import Panel
from bpy.props import StringProperty
from bpy.props import EnumProperty

import material_import

from rprblender import config
from rprblender import logging
from rprblender.material_editor import MaterialEditor
from rprblender.ui import activate_shader_editor
from .nodes import RPRPanel
from rprblender import rpraddon
from rprblender import node_unwrapping


# A material group is a set of materials in either a category or search result.
# The items property is the list of enumerated items used by the Blender UI.
# The data property is the corresponding list of material manifest data and a
# reference to the containing category.
class RPRMaterialGroup:

    def __init__(self, items, data):
        self.items = items
        self.data = data


# The material library loads the manifest and provides methods for creating
# property enumerations for categories and materials used by the Blender UI.
# It also provides caching to prevent repeated enumeration and preview loading,
# and methods for searching.
class RPRMaterialLibrary:

    def __init__(self):
        self.path = ""
        self.folder = "material_library"
        self.environment_variable = "RPR_MATERIAL_LIBRARY_PATH"
        self.library_not_found = False

        self.manifest = {}
        self.manifest_loaded = False

        self.category_items = []
        self.categories_loaded = False

        self.active_material_group = RPRMaterialGroup([], [])
        self.material_group_cache = {}

        self.selected_category_index = -1
        self.selected_material_index = -1

        self.search_changed = False
        self.search_string = ""
        self.search_result = []

        self.previews = bpy.utils.previews.new()
        self.material_preview_cache = {}

        self.load_manifest()

    # Load the material manifest from a Json file.
    def load_manifest(self):

        # Locate the library.
        self.locate_library()
        if self.library_not_found:
            return

        # Check that the manifest exists.
        manifest_file = self.path + "/manifest.json"

        if not os.path.isfile(manifest_file):
            logging.info("Material library manifest not found at {}".format(self.path), tag='material')
            return

        # Read the manifest.
        with open(manifest_file) as data_file:
            self.manifest = json.load(data_file)

        categories = self.manifest["categories"]

        categories = sorted(categories, key=lambda items: items['name'])

        self.manifest["categories"] = categories

        # Map categories to materials.
        for category in self.manifest["categories"]:
            for material in category["materials"]:
                material["category"] = category

        self.manifest_loaded = True

    # Check different possible locations for the library.
    def locate_library(self):
        # Look in the library install location.
        self.path = self.get_library_path()
        if len(self.path) > 0 and os.path.exists(self.path):
            return

        # Library not found.
        self.library_not_found = True

    # Get the library path from the registry or an environment variable.
    def get_library_path(self):

        # if there's configdev settings(or we just hardcoded in config, it can happen!)
        if config.material_library_path:
            return config.material_library_path

        # Use an environment variable, for development to override installed lib
        if self.environment_variable in os.environ:
            return os.environ[self.environment_variable]

        # Read the path from the registry if running in Windows.
        if 'Windows' == platform.system():

            import winreg

            # Open the key.
            key = None
            try:  # try ML2.0 registry path
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                     "SOFTWARE\\AMD\\RadeonProRender\\MaterialLibrary\\Blender")
            except OSError as e:
                logging.debug("Unable to find ML2.0 registry key: {}".format(e))
                pass
            except Exception as e:
                logging.debug("Unable to find ML2.0 registry key: {}".format(e))

            if not key:  # try the ML1.0 path
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "SOFTWARE\\AMD\\Radeon ProRender for Blender")
                except OSError as e:
                    logging.debug("Unable to find ML1.0 registry key: {}".format(e))
                    pass
                except Exception as e:
                    logging.debug("Unable to find ML1.0 registry key: {}".format(e))

            if key:
                try:
                    # Read the value.
                    result = winreg.QueryValueEx(key, "MaterialLibraryPath")

                    # Close the key.
                    winreg.CloseKey(key)

                    # Return value from the resulting tuple.
                    return result[0]
                except OSError as e:
                    logging.debug("Unable to load Material Library path from registry: {}".format(e))
                    pass
                except Exception as e:
                    logging.debug("Unable to load Material Library path from registry: {}".format(e))

        elif 'Linux' == platform.system():
            home = Path.home()
            install_dir_for_files = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share')) / 'rprblender'

            matlib_installed = install_dir_for_files / '.matlib_installed'
            if matlib_installed.exists():
                matlib_path = Path(matlib_installed.read_text())
                matlib_path = str(matlib_path)
                if matlib_path and os.path.exists(matlib_path + "/Xml"):  # Material Library 2.0
                    logging.info("Material Library 2.0 found", tag='material')
                    return matlib_path + "/Xml"
                logging.info("Material Library 1.0 found", tag='material')
                return matlib_path  # Material Library 1.0

        elif 'Darwin' == platform.system():
            if os.path.exists("/Users/Shared/RadeonProRender/Blender/matlib/Xml"):  # Material Library 2.0
                return "/Users/Shared/RadeonProRender/Blender/matlib/Xml"
            return "/Users/Shared/RadeonProRender/Blender/matlib"  # Material Library 1.0

        return ""

    # Get the category enumeration.
    def get_categories(self, context):

        # Check that the manifest is loaded and that
        # the categories have not already been loaded.
        if not self.manifest_loaded or self.categories_loaded:
            return self.category_items

        # Iterate over manifest categories
        # and populate the enumeration items.
        categories = self.manifest["categories"]

        for i, category in enumerate(categories):
            name = category["name"]
            if not category["materials"]:
                logging.debug("Ignoring empty material library category '{}'".format(name))
                continue
            self.category_items.append((str(i), name, "", 0, i))

        self.categories_loaded = True

        return self.category_items

    # Get the current material enumeration. This can be the result of
    # a search, or the materials in the currently selected category.
    def get_materials(self, context):

        mlp = context.window_manager.rpr_material_library_properties

        if mlp.mode == "categories":
            return self.get_category_materials(context)
        else:
            return self.get_search_materials(context)

    # Get an enumeration for the materials in the current category.
    def get_category_materials(self, context):
        # Ensure categories have loaded.
        if not self.categories_loaded:
            return self.active_material_group.items

        # Get the selected category index.
        index = int(context.window_manager.rpr_material_library_properties.categories)

        # Check if the index has changed since the last request.
        if self.selected_category_index == index:
            return self.active_material_group.items

        self.selected_category_index = index

        # Use cached values if possible, otherwise, get and cache new values.
        if index in self.material_group_cache:
            self.active_material_group = self.material_group_cache[index]
        else:
            self.active_material_group = self.get_material_group(self.manifest["categories"][index]["materials"])
            self.material_group_cache[index] = self.active_material_group

        # Reset the selected material to the first entry in the list.
        self.reset_selected_material(context)

        return self.active_material_group.items

    # Get an enumeration for the materials in the current search result.
    def get_search_materials(self, context):

        # Check that a search has been performed.
        if not self.search_changed:
            return self.active_material_group.items

        self.search_changed = False

        # Check that the search was successful.
        if not self.check_search(context):
            return self.active_material_group.items

        # Get the enumeration for the search result.
        self.active_material_group = self.get_material_group(self.search_result)

        # Reset the selected material to the first entry in the
        # list and reset the current category so the enumeration
        # gets reevaluated when the mode is switched back.
        self.reset_selected_material(context)
        self.selected_category_index = -1

        return self.active_material_group.items

    # Check the current search and results.
    def check_search(self, context):
        mlp = context.window_manager.rpr_material_library_properties

        # Check that the search string was valid.
        if len(self.search_string) < 2 or self.search_string.isspace():
            mlp.info_type = "invalid_search"
            return False

        # Check that there were search results.
        if len(self.search_result) <= 0:
            mlp.search_string = self.search_string
            mlp.info_type = "search_not_found"
            return False

        # The search was successful.
        return True

    # Get a material group for the specified material manifest data.
    def get_material_group(self, materials):

        # Generate enumeration items matched with manifest data.
        items = []
        data = []

        for i, material in enumerate(materials):
            name = material["name"]
            preview = self.get_material_preview(material)
            items.append((str(i), name, "", preview.icon_id, i))
            data.append(material)

        return RPRMaterialGroup(items, data)

    def get_material_xml(self, material):
        file_name = material["fileName"]
        return str(Path(self.path).joinpath(file_name, file_name + ".xml"))

    # Get an enumeration item for the specified material manifest data.
    def get_material_preview(self, material):

        # Find the icon file name.
        file_name = material["fileName"]
        file_path = self.path + "/" + file_name + "/" + file_name + ".jpg"

        # Return a cached preview if possible.
        if file_path in self.material_preview_cache:
            return self.material_preview_cache[file_path]

        # Load a new preview.
        preview = self.previews.load(file_path, file_path, "IMAGE", False)

        # Inspect the preview size. Without this, the
        # resulting image has a much lower resolution.
        preview.image_size[0]

        # Cache the preview.
        self.material_preview_cache[file_path] = preview

        return preview

    # Select a material.
    def select_material(self, context):

        # Set the selected material index and update info.
        mlp = context.window_manager.rpr_material_library_properties
        self.selected_material_index = int(mlp.materials)
        self.update_material_info(context)

    # Update material information.
    def update_material_info(self, context):

        material = self.active_material_group.data[self.selected_material_index]
        category = material["category"]

        mlp = context.window_manager.rpr_material_library_properties
        mlp.category_name = category["name"]
        mlp.material_name = material["name"]
        mlp.material_file = material["fileName"] + ".xml"

        mlp.info_type = "material"

    # Perform a search over all materials.
    def search_materials(self, search_string):

        # Ensure categories have loaded.
        if not self.categories_loaded:
            return

        # Store the search string so it can be passed to the
        # material library properties if no results were found.
        self.search_string = search_string
        self.search_changed = True
        self.search_result.clear()

        # Convert the search string to lower
        # case so the search is not case sensitive.
        search_string = search_string.lower()

        # Check that the string is long enough
        # to search and is not whitespace.
        if len(search_string) < 2 or search_string.isspace():
            return

        # Populate the search result.
        for category in self.manifest["categories"]:
            for material in category["materials"]:
                if search_string in material["name"].lower():
                    self.search_result.append(material)

    # Reset the selected material to the first one in the list.
    def reset_selected_material(self, context):
        context.window_manager.rpr_material_library_properties.materials = "0"
        self.selected_material_index = 0
        self.update_material_info(context)

    # Import the selected material into Blender.
    def import_material(self):
        # Check that there is a selected material.
        if self.selected_material_index < 0:
            return

        # Check that there are active materials.
        if len(self.active_material_group.data) <= self.selected_material_index:
            return

        material = self.active_material_group.data[self.selected_material_index]
        print("Import material " + material["fileName"])
        return material

    # Perform clean up operations before exiting.
    def clean_up(self):
        # Remove previews.
        bpy.utils.previews.remove(self.previews)
        self.material_preview_cache.clear()


# Material browser properties act as a binding between
# the material browser panel and the material library.
@rpraddon.register_class
class RPRMaterialBrowserProperties(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        # Add the properties to the window manager.
        bpy.types.WindowManager.rpr_material_library_properties = bpy.props.PointerProperty(
            name="Radeon ProRender Material Library",
            description="Radeon ProRender Material Library",
            type=cls,
        )

        # Category / search modes.
        cls.mode = EnumProperty(
            items=(("categories", "Categories", "Browse materials by category", 0),
                   ("search", "Search", "Search for materials by name", 1)))

        # Search string entry.
        cls.search = StringProperty(
            name="Search",
            set=cls.search_materials)

        # Category enumeration.
        cls.categories = EnumProperty(
            name="Categories",
            items=cls.get_categories)

        # Material enumeration.
        cls.materials = EnumProperty(
            name="Materials",
            items=cls.get_materials,
            update=cls.material_selected)

        # Category / search modes.
        cls.info_type = EnumProperty(
            items=(("material", "", "", 0),
                   ("invalid_search", "", "", 1),
                   ("search_not_found", "", "", 2)))

        # Material info.
        cls.category_name = StringProperty()
        cls.material_name = StringProperty()
        cls.material_file = StringProperty()

        # Search info.
        cls.search_string = StringProperty()

    @classmethod
    def unregister(cls):
        # Delete properties and clean up the library.
        del bpy.types.WindowManager.rpr_material_library_properties

    # Enumerate categories.
    @staticmethod
    def get_categories(self, context):
        return rpr_material_library.get_categories(context)

    # Enumerate materials.
    @staticmethod
    def get_materials(self, context):
        return rpr_material_library.get_materials(context)

    # A material was selected.
    @staticmethod
    def material_selected(self, context):
        rpr_material_library.select_material(context)

    # A search string was entered.
    @staticmethod
    def search_materials(self, value):
        rpr_material_library.search_materials(value)


# The material browser panel defines the UI layout. Data binding
# is performed by referencing the material library properties.
@rpraddon.register_class
class RPRMaterialBrowserPanel(RPRPanel, Panel):
    bl_label = "RPR Material Browser"
    bl_context = "material"
    bl_options = {'DEFAULT_CLOSED'}

    # Draw the panel.
    def draw(self, context):
        # Get the properties.
        mlp = context.window_manager.rpr_material_library_properties
        layout = self.layout

        # Show a message if the library wasn't found.
        if rpr_material_library.library_not_found:
            self.draw_library_not_found(layout)

        # Show the library when ready.
        elif rpr_material_library.manifest_loaded:
            self.draw_library(mlp, layout, context)

    # Draw the library not found message.
    def draw_library_not_found(self, layout):
        box = layout.box()
        box.label("Material library not found.")

    # Draw the material library.
    def draw_library(self, mlp, layout, context):

        # Mode buttons.
        row = layout.row()
        row.prop(mlp, "mode", expand=True)

        # Category selector.
        if mlp.mode == "categories":
            row = layout.row()
            row.prop(mlp, "categories", text="")

        # Search field.
        else:
            row = layout.row()
            row.prop(mlp, "search", text="", icon="VIEWZOOM")

        # Material preview.
        row = layout.row()
        sub = row.row()
        sub.scale_y = 1.95
        sub.template_icon_view(mlp, "materials", True, 5)

        # Info area.
        box = layout.box()
        row = box.row()

        # Invalid search info.
        if mlp.info_type == "invalid_search":
            col = row.column()
            col.label("Invalid search:")
            col.label("Please enter at least 2 characters.")
            col.label("")

        # Search results not found info.
        elif mlp.info_type == "search_not_found":
            col = row.column()
            col.label("Search: '" + mlp.search_string + "'")
            col.label("No materials found.")
            col.label("")

        # Material info.
        else:
            split = row.split(0.25)
            col = split.column()
            col.label("Category:")
            col.label("Name:")
            col.label("File:")
            col = split.column()
            col.label(mlp.category_name)
            col.label(mlp.material_name)
            col.label(mlp.material_file)

        # Import material button.
        column = layout.column()
        column.label("Import Material:")
        row = column.row()
        row.prop(context.scene.rpr, 'copy_textures', expand=True)
        column.operator("rpr.import_material_operator").copy_textures = context.scene.rpr.copy_textures


# The import material operator instructs the material library
# to import the currently selected material into Blender.
def import_xml_material(fpath, material, copy_textures=False):
    if not material.node_tree:
        material.use_nodes = True

    tree = material.node_tree
    tree.nodes.clear()
    material_editor = MaterialEditor(tree)

    def copy_image(src, dst):
        logging.info('copy image:', src, dst, tag='material')
        dst_full_path = os.path.join(bpy.path.native_pathsep(bpy.path.abspath('//')), dst)
        dst_folder = os.path.dirname(dst_full_path)
        if not os.path.isdir(dst_folder):
            os.makedirs(dst_folder)
        if not os.path.exists(dst_full_path):
            source_path = bpy.path.native_pathsep(src)
            shutil.copyfile(source_path, dst_full_path)
        return '//' + dst.replace(os.path.sep, '/')

    with open(fpath) as xml:
        logging.info('loading material...', fpath)
        loader = material_import.MaterialImageLoader(load_image=material_editor.load_image,
                                                     root_folder=rpr_material_library.path,
                                                     material_folder=os.path.dirname(fpath),
                                                     copy_image=copy_image if copy_textures else None)
        shader = material_import.compile_material_from_xml(
            xml.read(), material_editor,
            loader)
    logging.info('finish loading material...')

    shader.node.location = 300, 400

    output = tree.nodes.new('rpr_shader_node_output')
    output.location = 550, 400

    tree.links.new(shader.get_output_socket(), output.inputs[0])
    activate_shader_editor()

    # we need few times update scene before call nodes arrange, because node dimension hasn't updated yet
    bpy.ops.rpr.node_arrange(margin_vertical=350, margin_horizontal=550)


@rpraddon.register_class
class RPRImportXMLMaterialOperator(bpy.types.Operator):
    bl_idname = "rpr.import_xml_material"
    bl_label = "RPR Import XML Material"
    xml_path = bpy.props.StringProperty(name="xml_path")

    # Perform the operator action.
    def execute(self, context):
        import_xml_material(self.xml_path, context.material)
        return {'FINISHED'}


# The import material operator instructs the material library
# to import the currently selected material into Blender.
@rpraddon.register_class
class RPRImportMaterialOperator(bpy.types.Operator):
    bl_idname = "rpr.import_material_operator"
    bl_label = "RPR Import Selected Material"

    copy_textures = bpy.props.EnumProperty(
        name="XXX",
        items=(('DEFAULT', "Don't copy textures", "Reference original texture images of material library"),
               ('LOCAL', "Copy textures locally", "Copy texture images under blend file folder if scene is saved.\n"
                                                  "Reference original texture images if not.")),
        description="Choose to copy texture images to blend file folder",
        default='DEFAULT',
    )

    # Perform the operator action.
    def execute(self, context):
        blender_material = context.material
        import_material = rpr_material_library.import_material()
        if not blender_material:
            logging.info('create new blender material...')
            name = import_material["name"].lower()
            context.object.active_material = bpy.data.materials.new(name)
            blender_material = context.object.active_material

        import_xml_material(rpr_material_library.get_material_xml(import_material), blender_material,
                            copy_textures=self.copy_textures == 'LOCAL')
        return {'FINISHED'}


@rpraddon.register_class
class RPRImportMaterialsTestOperator(bpy.types.Operator):
    bl_idname = "rpr.import_materials_test_operator"
    bl_label = "RPR Import Materials Test"

    @classmethod
    def poll(cls, context):
        return context.material != None

    last_index = 0
    done_all = False

    # Perform the operator action.
    def execute(self, context):
        index = 0
        for category in rpr_material_library.manifest["categories"]:
            for material in category["materials"]:
                if RPRImportMaterialsTestOperator.last_index <= index:
                    logging.info('Import material: --- %s (%d)---' % (material['name'], index))
                    import_xml_material(rpr_material_library.get_material_xml(material), context.material)
                    RPRImportMaterialsTestOperator.last_index += 1
                    return {'FINISHED'}

                index += 1
        RPRImportMaterialsTestOperator.done_all = True
        return {'FINISHED'}


@rpraddon.register_class
class RPRImportAxfMaterialOperator(bpy.types.Operator):
    bl_idname = "rpr.import_axf_material"
    bl_label = "RPR Import AxF Material"

    filepath = bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        import axf

        fpath = self.filepath
        print(fpath)

        axf_converter_bin_path = Path(__file__).parent / '_axf_converter/ReleaseDll/AxfDll'
        if not axf_converter_bin_path.is_dir():  # in case running from source
            axf_converter_bin_path = Path(__file__).parents[2] / 'Externals/AxfPackage/ReleaseDll/AxfDll'
        converter = axf.AxfConverter(
            axf_converter_bin_path=str(axf_converter_bin_path))
        xml_path = converter.convert(fpath).decode('utf8')
        assert xml_path
        bpy.ops.rpr.import_xml_material('EXEC_DEFAULT', xml_path=xml_path)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


rpr_material_library = None


def register():
    logging.info('material_browser.register')
    # The material library instance, referenced by the browser properties.
    global rpr_material_library
    rpr_material_library = RPRMaterialLibrary()


def unregister():
    logging.info('material_browser.unregister')
    global rpr_material_library
    rpr_material_library.clean_up()
    rpr_material_library = None
