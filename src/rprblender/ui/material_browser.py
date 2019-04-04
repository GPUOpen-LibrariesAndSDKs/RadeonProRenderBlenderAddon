from . import RPR_Panel
from rprblender import material_library

from rprblender.utils.logging import Log
log = Log(tag="material_library")


class RPR_MATERIL_PT_material_browser(RPR_Panel):
    """ Panel for Material Library materials browse, search and import """
    bl_label = "Material Library Browser"
    bl_context = "material"
    # bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        # Inform user if Library
        if not material_library.rpr_material_library.is_valid:
            box = layout.box()
            box.label(text="Material library not found.")
            layout.operator('rpr.op_open_web_page', text="Downloads").page = 'downloads'
            return

        properties = context.window_manager.rpr_material_library_properties

        # TODO: implement material search
        # Mode buttons.
        row = layout.row()
        row.prop(properties, "mode", expand=True)

        show_preview = properties.mode == "CATEGORIES" or properties.info_type == "MATERIAL"

        # Category selector.
        if properties.mode == "CATEGORIES":
            row = layout.row()
            row.prop(properties, "categories", text="")

        # Search field.
        else:
            row = layout.row()
            row.prop(properties, "search", text="", icon="VIEWZOOM")

            # search string is too short info
            if properties.info_type == "INVALID_SEARCH":
                layout.label(text="Invalid search:")
                layout.label(text="Please enter at least 2 characters.")
                layout.label(text="")

            # Search results not found info
            elif properties.info_type == "SEARCH_NOT_FOUND":
                layout.label(text="Search: '" + properties.search_string + "'")
                layout.label(text="No materials found.")
                layout.label(text="")

            # Display search string for current results
            else:
                layout.label(text="Search: '" + properties.search_string + "'")

        if show_preview:
            row = layout.row()
            sub = row.row()
            sub.scale_y = 1.95
            sub.template_icon_view(properties, "materials", show_labels=True, scale=5)

        # Import material button.
        column = layout.column()
        column.label(text="Import Material:")

        # "Copy textures to scene location" checkbox
        row = column.row()
        row.prop(properties, 'copy_textures')

        row = layout.row()
        row.operator("rpr.import_material_operator")
        # disable button for wrong search results
        if not show_preview:
            row.enabled = False
