import os
import platform
import shutil

import bpy

from rprblender.utils.logging import Log
log = Log(tag="material_library")


class MaterialImageLoader:
    """ Load images for material, copy it to scene file location if requested """
    def __init__(self, root_folder: str, material_folder: str, copy_locally=False):
        self.is_os_windows = 'Windows' == platform.system()
        self.root_folder = ''.join(root_folder.split('Xml')[:-1])
        self.material_folder = material_folder
        self.copy_locally = copy_locally

    def load_image(self, file_name: str) -> bpy.types.Image:
        """ Load image from library by relative path or copy to scene location and load """
        is_copy_allowed = self.copy_locally and bpy.path.abspath('//')  # copy enabled and scene is saved?
        is_path_relative = '\\' in file_name or '/' in file_name  # is texture in common folder?

        if is_path_relative:
            file_path = file_name.split("..")[-1]
        else:
            file_path = file_name

        separator = '/'
        if self.is_os_windows:  # on Windows use Windows path separator for correct work
            file_path = file_path.replace('/', '\\')
            separator = '\\'

        if not is_copy_allowed:
            if is_path_relative:
                path_full = self.root_folder + file_path
            else:
                path_full = self.material_folder + separator + file_path
            return bpy.data.images.load(path_full)

        # try to copy texture to scene location
        if is_path_relative:
            path_full = self.root_folder + file_path
            path_relative = file_path
        else:
            path_full = self.material_folder + separator + file_path
            path_relative = os.path.basename(self.material_folder) + separator + file_path

        path_relative = 'rprmaterials' + separator + path_relative

        try:
            copied_image_path = self.copy_image(path_full, path_relative)
            return bpy.data.images.load(copied_image_path)
        except PermissionError:  # access denied, most likely user hasn't saved new scene yet
            # TODO: inform user she should save scene .blend file first
            return bpy.data.images.load(path_full)

    @staticmethod
    def copy_image(src: str, dst: str) -> str:
        log.info('copy image:', src, dst)
        dst_full_path = os.path.join(bpy.path.native_pathsep(bpy.path.abspath('//')), dst)
        dst_folder = os.path.dirname(dst_full_path)
        if not os.path.isdir(dst_folder):
            os.makedirs(dst_folder)
        if not os.path.exists(dst_full_path):
            source_path = bpy.path.native_pathsep(src)
            shutil.copyfile(source_path, dst_full_path)
        return '//' + dst.replace(os.path.sep, '/')
