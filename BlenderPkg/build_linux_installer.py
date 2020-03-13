#/usr/bin/python3

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
