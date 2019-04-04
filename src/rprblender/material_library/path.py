import os
import platform
from pathlib import Path

from rprblender.config import material_library_path

from rprblender.utils.logging import Log
log = Log(tag="utils.material_library")


# use environment variable to override library path for debug/testing purpose
DEV_ENVIRONMENT_VARIABLE = "RPR_MATERIAL_LIBRARY_PATH"

# Windows registry keys, library versions 1.0 and 2.0
WIN_MATLIB_1_REGKEY = "SOFTWARE\\AMD\\Radeon ProRender for Blender"
WIN_MATLIB_2_REGKEY = "SOFTWARE\\AMD\\RadeonProRender\\MaterialLibrary\\Blender"

# Ubuntu has 3 possible material library locations
UBUNTU_MATLIB_1 = "/Users/Shared/RadeonProRender/Blender/matlib"
UBUNTU_MATLIB_2_INTEGRATED = "/Users/Shared/RadeonProRender/Blender/matlib/Xml"
UBUNTU_MATLIB_2_SEPARATED = "/Users/Shared/RadeonProRender/MaterialLibrary/2.0.0/Xml"


def get_library_path() -> str:
    """ Check the possible platform-dependant library locations, return location if found, empty string otherwise """

    # if config/configdev override setting used
    if material_library_path:
        log("config.material_library_path: {}".format(material_library_path))
        return material_library_path

    # if debug/development environment override used
    if DEV_ENVIRONMENT_VARIABLE in os.environ:
        return os.environ[DEV_ENVIRONMENT_VARIABLE]

    # Read the path from the registry if running in Windows.
    if 'Windows' == platform.system():
        import winreg

        # Open the key.
        key = None
        try:  # try ML2.0 registry path
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, WIN_MATLIB_2_REGKEY)
        except OSError as e:
            log("Unable to find ML2.0 registry key: {}".format(e))

        if not key:  # try the ML1.0 path
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_MATLIB_1_REGKEY)
            except OSError as e:
                log("Unable to find ML1.0 registry key: {}".format(e))

        if key:
            try:
                # get the value from registry by key
                result = winreg.QueryValueEx(key, "MaterialLibraryPath")
                winreg.CloseKey(key)
            except OSError as e:
                log("Unable to load Material Library path from registry: {}".format(e))
            else:
                if result and result[0] and isinstance(result[0], str):
                    path = result[0]
                    if os.path.isdir(path):
                        return path

    elif 'Linux' == platform.system():
        home = Path.home()
        install_dir_for_files = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share')) / 'rprblender'

        matlib_installed = install_dir_for_files / '.matlib_installed'
        if matlib_installed.exists():
            matlib_path = Path(matlib_installed.read_text())
            matlib_path = str(matlib_path)
            if matlib_path and os.path.isdir(matlib_path + "/Xml"):  # Material Library 2.0
                log.info("Material Library 2.0 found")
                return matlib_path + "/Xml"

            # Material Library 1.0
            log.info("Material Library 1.0 found")
            if os.path.isdir(matlib_path):
                return matlib_path

    elif 'Darwin' == platform.system():
        # Material Library 2.0 separate lib
        if os.path.isdir(UBUNTU_MATLIB_2_SEPARATED):
            return UBUNTU_MATLIB_2_SEPARATED

        # Material Library 2.0 embedded lib
        if os.path.isdir(UBUNTU_MATLIB_2_INTEGRATED):
            return UBUNTU_MATLIB_2_INTEGRATED

        # Material Library 1.0
        if os.path.isdir(UBUNTU_MATLIB_1):
            return UBUNTU_MATLIB_1

    return ""


