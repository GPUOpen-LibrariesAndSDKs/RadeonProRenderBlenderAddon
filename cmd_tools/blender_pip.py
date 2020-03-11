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
import subprocess
import urllib.request
import tempfile
import os


GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
python_exe = sys.executable


def try_install_pip():
    try:
        import pip
        print("Module pip is already installed")
        return

    except ImportError:
        pass

    print("Downloading get-pip.py")
    file_name = tempfile.gettempdir() + "/get-pip.py"
    urllib.request.urlretrieve(GET_PIP_URL, file_name)

    try:
        print("Installing pip")
        subprocess.check_call([python_exe, file_name])

    finally:
        os.remove(file_name)


def try_install_boto3():
    try:
        import boto3
        print("Module boto3 is already installed")
        return

    except ImportError:
        pass

    print("Installing boto3")
    subprocess.check_call([python_exe, '-m', 'pip', 'install', 'boto3'])


def main():
    try_install_pip()
    try_install_boto3()


if __name__ == "__main__":
    main()
