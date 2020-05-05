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
import site
import subprocess

import bpy
from . import IS_MAC, IS_LINUX

from rprblender.utils.logging import Log
log = Log(tag="install_libs")


# adding user site-packages path to sys.path
if site.getusersitepackages() not in sys.path:
    sys.path.append(site.getusersitepackages())


def run_module_call(*args):
    """Run Blender Python with arguments on user access level"""
    module_args = ('-m', *args, '--user')
    log(f"Running subprocess.check_call {module_args}")

    subprocess.check_call([bpy.app.binary_path_python, *module_args], timeout=60.0)


def run_pip(*args):
    """Run 'pip install' with current user access level"""
    return run_module_call('pip', 'install', *args)


def ensure_boto3():
    """
    Try to install boto3 library at the addon launch time.
    Use this snippet to install boto3 library with all the dependencies if absent at the addon launch time
    Note: still it will be available at the next Blender launch only
    """
    try:
        import boto3

    except ImportError:
        log.info("Installing boto3 library...")
        try:
            if IS_MAC or IS_LINUX:
                # Blender for Linux and MacOS have ensurepip module. Linux has no pip
                run_module_call('ensurepip', '--upgrade')

            run_pip("--upgrade", "pip")
            run_pip("wheel")
            run_pip('boto3')
            log.info("Library boto3 installed and ready to use.")

        except subprocess.SubprocessError as e:
            log.warn("Something went wrong, unable to install boto3 library.", e)
