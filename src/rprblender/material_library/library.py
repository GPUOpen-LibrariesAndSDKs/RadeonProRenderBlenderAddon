#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
from bpy.utils import previews  # for some reason Blender doesn't allow access via bpy.utils.previews
import json
import os
from pathlib import Path

from .path import get_library_path

from rprblender.utils.logging import Log
log = Log(tag="material_library")


class MaterialEntry:
    """ Material entry info """
    def __init__(self, name: str, file_name: str, category: str):
        self.name = name
        self.file_name = file_name
        self.category = category


class RPRMaterialLibrary:
    """ Locate, parse and store material library info """

    def __init__(self):
        self.is_valid = False  # Is library loaded succesfully?

        self.path = ""  # library root directory path
        self.categories = {}
        self.materials = {}

        self.previews = previews.new()
        self.material_preview_cache = {}

        # info for currently selected category
        self.active_category = ""  # current
        self.active_materials = {}

        self.is_valid = self.load_manifest()

    # Perform clean up operations before exiting.
    def clean_up(self):
        # Remove previews.
        previews.remove(self.previews)
        self.material_preview_cache.clear()

    def load_manifest(self) -> bool:
        """ Load the material manifest from Json file, return loading success status """

        # Locate the library.
        self.path = get_library_path()
        if not self.path:
            return False
        log.info("Material library located at {}".format(self.path))

        # Check that the manifest exists.
        manifest_file = self.path + "/manifest.json"
        if not os.path.isfile(manifest_file):
            log.error("Unable to find Material Library manifest at {}".format(self.path))
            return False

        # Read the manifest.
        with open(manifest_file) as data_file:
            manifest = json.load(data_file)

        log("categories: {}".format([entry['name'] for entry in manifest["categories"]]))

        # parse sorted categories to store materials info
        for category in sorted(manifest["categories"], key=lambda items: items['name']):
            entry_materials = []
            for material in category['materials']:
                info = MaterialEntry(material['name'], material['fileName'], category['name'])
                self.materials[material['name']] = info
                entry_materials.append(info)

            # store info for non-empty categories only
            if entry_materials:
                self.categories[category['name']] = entry_materials

        return True

    def get_categories_items(self) -> tuple:
        """ Enumerate library categories for UI using category name as ID, name and description """
        return tuple((name, name, name, i) for i, name in enumerate(self.categories.keys()))

    def prepare_active_materials_enum_entries(self, source):
        """ Enumerate source for materials, store ready EnumProperty tuples"""
        self.active_materials = {}
        for i, entry in enumerate(source):
            preview = self.get_material_preview(entry)
            self.active_materials[str(i)] = (entry.name, preview.icon_id, i)

    def set_active_category(self, category_name: str):
        """ If selected category was changed - prepare browsing data for new category """
        # is info already prepared?
        if self.active_category == category_name:
            return

        # collect new active materials group
        self.active_category = category_name
        self.prepare_active_materials_enum_entries(self.categories[category_name])

    def search_materials(self, search_string: str):
        """ Create search category if changed, prepare browsing data for it """
        if len(search_string) < 2:
            return 'INVALID_SEARCH'
        category_name = 'SEARCH.{}'.format(search_string)

        # have we already prepared info for this search?
        if self.active_category == category_name:
            return

        # collect new active materials search group
        filtered_materials = tuple(mat for mat in self.materials.values() if search_string.lower() in mat.name.lower())

        # to prevent UI from spamming warning for empty search result don't do anything
        if not filtered_materials:
            return 'SEARCH_NOT_FOUND'

        # otherwise update active materials
        self.active_category = category_name
        self.prepare_active_materials_enum_entries(filtered_materials)
        return 'MATERIAL'

    def get_category_materials(self, category_name: str) -> tuple:
        """ Set active category if new, return active category materials for UI by category name"""
        self.set_active_category(category_name)

        # this way UI will be able to reset material to first in category on category change
        return tuple((key, entry[0], entry[0], entry[1], entry[2]) for key, entry in self.active_materials.items())

    def get_search_materials(self) -> tuple:
        """ Return active materials for search results """
        return tuple((key, entry[0], entry[0], entry[1], entry[2]) for key, entry in self.active_materials.items())

    def get_material_xml(self, enum_id: str) -> (str, str):
        """ Return direct path to material xml file and material name by material enum id """
        material_name = self.active_materials[enum_id][0]
        info = self.materials[material_name]
        return str(Path(self.path).joinpath(info.file_name, info.file_name + ".xml")), material_name

    def get_material_preview(self, material: MaterialEntry):
        """ Load preview image for material, return preview object """
        # Find the icon file name.
        file_name = material.file_name
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

