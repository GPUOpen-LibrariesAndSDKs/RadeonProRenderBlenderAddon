#/usr/bin/python3

import os
import argparse
import shutil
import subprocess
from pathlib import Path

import create_build_output

parser = argparse.ArgumentParser()
parser.add_argument('--nocomp', action='store_true')

args = parser.parse_args()

installer_build_dir = Path("./.installer_build")

if installer_build_dir.exists():
    shutil.rmtree(str(installer_build_dir))

plugin_version, plugin_version_parts = create_build_output.ReadAddOnVersion()

dist_dir = installer_build_dir / 'dist'

addon_files_dist_dir = dist_dir / 'addon'
addon_files_dist_dir.mkdir(parents=True)
material_library_dist_dir = dist_dir / 'matlib'

externals_path = Path('./Externals')

create_build_output.create_zip_addon(str(addon_files_dist_dir / 'addon.zip'),
                                     plugin_version, target='linux')
installer_src_path = Path('./linux-support')
for name in ['install.py', 'uninstall.py', 'eula.txt']:
    shutil.copy(str(installer_src_path / name), str(dist_dir))


lib_path_hint = ''
if 'AMDAPPSDKROOT' in os.environ:
    lib_path_hint = os.environ['AMDAPPSDKROOT']

checker_path = installer_src_path / 'Checker'
checker_build_path = checker_path / '.build'
checker_build_path.mkdir(exist_ok=True)
subprocess.check_call(['cmake', '-DCMAKE_LIBRARY_PATH='+ lib_path_hint +'/lib/x86_64-linux-gnu', '..'], cwd=str(checker_build_path))
subprocess.check_call(['make'], cwd=str(checker_build_path))

for name in ['remove_blender_addon.py', 'Checker/.build/checker']:
    shutil.copy(str(installer_src_path / name), str(addon_files_dist_dir))

create_build_output.CreateMaterialLibrary(str(material_library_dist_dir))

installer_path = installer_build_dir / (
'RadeonProRenderForBlender_%s.run' % plugin_version)

makeself_cmd = (['makeself']
                +(['--nocomp'] if args.nocomp else
                  ['--gzip', '--complevel', '1'])
                +[
                str(dist_dir), str(installer_path),
                'Radeon ProRender for Blender',
                './install.py',
                ])

print(makeself_cmd)
subprocess.check_call(makeself_cmd)

# archive_path = installer_build_dir / ('RadeonProRenderForMaya.Linux.%s.tar.gz' % plugin_version)
# with tarfile.open(str(archive_path), 'w') as arch:
#     arch.add(str(installer_path), arcname=installer_path.name)


# TODO:
# - add build to create installer
# + checker
# + register
# + key
# - get fresh eula
# - record blender path for uninstall
# + skip registration on consequent runs

# + allow blender addon install over installed
# + remove/readd addon to blender
# + eula
# + uninstall
# + install OpenImageIO
# + uninstall previous addon, see disableBlenderAddOn
# + location. ~/.local/share - https://askubuntu.com/a/14536/136352
# + embree - package
# + install material library - ~/Documents/Radeon ProRender/Blender/Material Library
# + don't overwrite material library if present(ask user)
# + use installed library
