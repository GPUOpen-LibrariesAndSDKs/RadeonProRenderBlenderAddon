import bpy
from bpy.props import (
    EnumProperty,
    PointerProperty,
    StringProperty,
    BoolProperty
)
from rprblender import material_library

from rprblender.utils.logging import Log
log = Log(tag="material.library")


class RPR_MaterialBrowserProperties(bpy.types.PropertyGroup):
    """ Material library browsing properties for UI """

    def get_categories(self, context):
        """ Get available non-empty library categories """
        return material_library.rpr_material_library.get_categories_items()

    def get_materials(self, context):
        """ Get library materials for active category or last search results """
        properties = context.window_manager.rpr_material_library_properties
        if properties.mode == "CATEGORIES":
            return material_library.rpr_material_library.get_category_materials(properties.categories)
        else:
            return material_library.rpr_material_library.get_search_materials()

    def category_selected(self, context):
        properties = context.window_manager.rpr_material_library_properties
        material_library.rpr_material_library.set_active_category(properties.categories)

        # select first material in updated category
        self.materials = '0'

    def search_materials(self, search_string):
        """ Search for materials by name """
        self.search_string = search_string  # to remind user what she was looking for
        self.info_type = material_library.rpr_material_library.search_materials(search_string)

    # Category / search modes.
    mode: EnumProperty(
        name="Library browsing mode",
        items=(
            ('CATEGORIES', "Categories", "Browse materials by category"),
            ('SEARCH', "Search", "Search for materials by name"),
        ),
        default='CATEGORIES',
    )

    categories: EnumProperty(
        name="Categories",
        items=get_categories,
        update=category_selected,
    )

    # Search string entry.
    search: StringProperty(
        name="Search",
        set=search_materials,
    )

    # Material enumeration.
    materials: EnumProperty(
        name="Materials",
        items=get_materials,
    )

    # Search success
    info_type: EnumProperty(
        items=(
            ('MATERIAL', "", "", 0),
            ('INVALID_SEARCH', "", "", 1),
            ('SEARCH_NOT_FOUND', "", "", 2)
        )
    )

    # Search info.
    search_string: StringProperty()

    copy_textures: BoolProperty(
        name="Copy textures to scene location",
        description="Choose to copy texture images to blend file folder",
        default=False,
    )

    @classmethod
    def register(cls):
        # Add the properties to the window manager
        log("RPRMaterialBrowserProperties.register()")
        bpy.types.WindowManager.rpr_material_library_properties = PointerProperty(
            name="Radeon ProRender Material Library",
            description="Radeon ProRender Material Library",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        # Delete properties
        log("RPRMaterialBrowserProperties.unregister()")
        del bpy.types.WindowManager.rpr_material_library_properties
