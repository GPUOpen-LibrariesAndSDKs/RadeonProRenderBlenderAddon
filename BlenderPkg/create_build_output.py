#!python3

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

import sys
import os
import platform
import subprocess
import datetime
import shutil
import errno
import re
import tempfile
import zipfile
import io

from pathlib import Path

materialLibraryXML = "../MaterialLibrary/2.0/xml_catalog_output"
materialLibraryMaps = "../MaterialLibrary/2.0/Maps"

repo_root = Path('..')


def repo_root_pushd():
    os.chdir(str(repo_root))


def repo_root_popd():
    os.chdir("BlenderPkg")


def Copy(src, dest):
    try:
        shutil.copytree(src, dest)
    except OSError as e:
        # If the error was caused because the source wasn't a directory
        if e.errno == errno.ENOTDIR:
            shutil.copy(src, dest)
        else:
            raise NameError('Directory not copied. Error: %s' % e)


if platform.system() in ("Linux", "Darwin"):
    import pwd

    def get_user_name():
        return pwd.getpwuid(os.getuid())[0]
else:
    def get_user_name():
        return os.getlogin()


def enumerate_addon_data(version, target):
    pyrpr_path = repo_root / 'src/bindings/pyrpr'

    dll_ext = {'windows': '.dll', 'linux': '.so', 'darwin': '.dylib'}[target]

    """repo_root_pushd()

    git_commit = subprocess.check_output('git rev-parse HEAD'.split())
    git_tag = subprocess.check_output('git describe --tags --match builds/*'.split())

    repo_root_popd()"""

    version_text = """version=%r
user=%s
timestamp=%s
target=%s
    """%(
        version,
        repr(get_user_name()),
        tuple(datetime.datetime.now().timetuple()),
        repr(target)
        )
    yield version_text.encode('utf-8'), 'version.py'

    #test version a bit
    version_dict = {}
    exec(version_text, {}, version_dict)
    assert version == version_dict['version']

    # copy pyrpr files
    pyrpr_folders = [pyrpr_path/'.build', pyrpr_path/'src']
    for pyrpr_folder in pyrpr_folders:
        for root, dirs, names in os.walk(str(pyrpr_folder)):
            for name in names:
                if any(ext in Path(name).suffixes for ext in ['.py', '.pyd', '.json', dll_ext]):
                    yield Path(root)/name, Path(root).relative_to(pyrpr_folder)/name

    # copy RPRBlenderHelper files
    if 'windows' == target:
        rprblenderhelper_folder = repo_root / 'RPRBlenderHelper/.build/Release'
        rprblenderhelper_files = ['RPRBlenderHelper.dll']
    elif 'darwin' == target:
        rprblenderhelper_folder = repo_root / 'RPRBlenderHelper/.build'
        rprblenderhelper_files = ['libRPRBlenderHelper.dylib']
    else:
        rprblenderhelper_folder = repo_root / 'RPRBlenderHelper/.build'
        rprblenderhelper_files = ['libRPRBlenderHelper.so']

    for name in rprblenderhelper_files:
        root = rprblenderhelper_folder
        yield Path(root)/name, name

    # copy addon python code
    rprblender_root = str(repo_root / 'src/rprblender')
    for root, dirs, names in os.walk(rprblender_root):
        for name in names:
            if name == 'configdev.py':
                continue

            if name.endswith('.py') or name == 'athena.bin':
                yield Path(root)/name, Path(root).relative_to(rprblender_root)/name

    # copy img folder
    img_root = str(repo_root / 'src/rprblender/img' )
    for root, dirs, names in os.walk(img_root):
        for name in names:
            if Path(name).suffix in ['.hdr', '.jpg', '.png', '.bmp', '.tga']:
                yield Path(root)/name, Path(root).relative_to(img_root)/'img'/name

    # copy Core and RIF dll's
    for lib in (repo_root / ".sdk/rpr/bin").glob("*"):
        yield lib, lib.name

    for lib in (repo_root / ".sdk/rif/bin").glob("*"):
        yield lib, lib.name

    if target in ('windows', 'linux'):
        # copy ML denoiser model data
        model_root = str(repo_root / '.sdk/rif/models')
        for root, dirs, names in os.walk(model_root):
            for name in names:
                yield Path(root)/name, Path('data/models')/Path(root).relative_to(model_root)/name

    # copy other files
    rprblender_root = str(repo_root / 'src/rprblender')
    for root, dirs, names in os.walk(rprblender_root):
        for name in names:
            if name == 'EULA.html':
                yield Path(root)/name, Path(root).relative_to(rprblender_root)/name
            elif name in ['RadeonProRender_ci.dat', 'RadeonProRender_co.dat', 'RadeonProRender_cs.dat']:
                yield Path(root)/name, Path(root).relative_to(rprblender_root)/name

    print("enumerate_addon_data OK")


def CreateAddOnModule(addOnVersion, build_output_folder):
    sys.dont_write_bytecode = True

    print('Creating build_output for AddOn version: %s' % addOnVersion)

    build_output_rpblender = os.path.join(build_output_folder, 'rprblender')
    if os.access(build_output_rpblender, os.F_OK):
        shutil.rmtree(build_output_rpblender)

    os.makedirs(build_output_rpblender, 0x777)

    dst_fpath = build_output_rpblender + '/addon.zip'
    print('dst_fpath: ', dst_fpath)
    shutil.copy2('./addon.zip', dst_fpath)


def ReadAddOnVersion():
    print("ReadAddOnVersion...")

    pyInitFileName = repo_root / 'src/rprblender/__init__.py'
    result = None
    with open( str(pyInitFileName), "r" ) as pyFile:
        s = pyFile.read()

        val = re.match( "(?s).*\"version\":\s\(([^)]+)\),", s )
        if val == None:
            raise NameError("Can't get addOnVersion")

        version = val.group(1)
        versionParts = version.split(",")
        if(len(versionParts) != 3):
            raise NameError("Invalid version string in __init__.py")

        sPluginVersionMajor = versionParts[0].rstrip().lstrip()
        sPluginVersionMinor = versionParts[1].rstrip().lstrip()
        sPluginVersionBuild = versionParts[2].rstrip().lstrip()

        sPluginVersion = sPluginVersionMajor + "." + sPluginVersionMinor + "." + sPluginVersionBuild

        result = sPluginVersion, (sPluginVersionMajor, sPluginVersionMinor, sPluginVersionBuild)

        print("  addOnVersion: \"%s\"" % sPluginVersion)

        print("ReadAddOnVersion ok.")
    return result


def create_zip_addon(package_name, version, target='windows'):
    """ Pack addon files to zip archive """
    with zipfile.ZipFile(package_name, 'w') as myzip:
        for src, package_path in enumerate_addon_data(version, target=target):
            print('adding ', package_path)
            if isinstance(src, bytes):
                print('  bytes')
                myzip.writestr(str(Path('rprblender') / package_path), src)
            else:
                print('  file', src)
                myzip.write(str(src), arcname=str(Path('rprblender') / package_path))
