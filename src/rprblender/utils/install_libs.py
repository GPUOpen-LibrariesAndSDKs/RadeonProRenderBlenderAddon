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
import bpy

import platform

from rprblender.utils.logging import Log
log = Log(tag="install_libs")


PYTHON_PATH = bpy.app.binary_path_python


def run_python_call(*args) -> bool:
    """
    Run Blender Python with arguments on user access level
    """
    import subprocess

    log(f"Running the subprocess.call '{args} --user'")

    try:
        subprocess.check_call([PYTHON_PATH, '-m', *args, '--user'])
        return True
    except subprocess.CalledProcessError as e:
        log.warn(f"\nSubprocess call '{args}' failed:\n\t{e}")

    return False


def run_pip(*args):
    """
    Run 'pip install' with current user access level
    """
    return run_python_call('pip', 'install', *args)


def ensure_boto3() -> None:
    """
    Try to install boto3 library at the addon launch time
    """
    # use this snippet to install boto3 library with all the dependencies if absent at the addon launch time
    # note: still it will be available at the next Blender launch only
    try:
        import boto3
    except (ImportError, ModuleNotFoundError):
        log.info("Installing boto3 library...")
        running_os = platform.system()
        if running_os in ('Linux', 'Darwin'):  # Blender for Linux and MacOS have ensurepip module. Linux has no pip
            if run_python_call('ensurepip', '--upgrade') and run_pip("--upgrade", "pip") and run_pip('boto3'):
                log.info("Library boto3 installed and ready to use.")
                return
        elif run_pip("--upgrade", "pip") and run_pip("boto3"):  # Blender for Windows has pip and no ensurepip module
            # Note: at this point library can be loaded by direct path usage, for example:
            # hardcoded_path = "C:\\Users\\<user_name>\\AppData\\Roaming\\Python\\Python37\\site-packages"
            # importlib.sys.path.append(hardcoded_path)
            # globals()['boto3'] = importlib.import_module('boto3')

            # after Blender restart no path modification would be needed. Report and let it be.
            log.info("Library boto3 should be available after Blender restart.")
            return

        log.warn("Something went wrong, unable to install boto3 library.")
