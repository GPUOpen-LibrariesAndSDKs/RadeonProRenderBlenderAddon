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
from pathlib import Path


arch = platform.architecture()
uname = platform.uname()


assert '64bit' == arch[0] and (('Windows' in uname[0]) or ('Linux' in uname[0]) or ('Darwin' in uname[0])), arch

subprocess.check_call([sys.executable, 'src/tools/encrypt_athena_bin.py'])

pyrpr_path = Path('src/bindings/pyrpr')

cwd = os.getcwd()
os.chdir(str(pyrpr_path))
pyrpr_build_dir = Path('.build')

subprocess.check_call([sys.executable, 'rpr.py'])
subprocess.check_call([sys.executable, 'rpr_load_store.py'])
os.chdir(cwd)

if sys.version_info.major == 3 and sys.version_info.minor == 7:
    # we are going to build RPRBlenderHelper only for python 3.7
    os.chdir('RPRBlenderHelper')
    os.makedirs('.build', exist_ok=True)
    os.chdir('.build')
    if 'Windows' == platform.system():
        subprocess.check_call(['cmake', '-G', 'Visual Studio 14 2015 Win64',  '..'])
    else:
        subprocess.check_call(['cmake', '..'])
    subprocess.check_call(['cmake', '--build',  '.', '--config', 'Release', '--clean-first'])
