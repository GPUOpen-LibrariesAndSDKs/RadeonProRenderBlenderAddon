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
from pathlib import Path
import subprocess
import platform
import shutil


OS = platform.system()
PROC = platform.uname().machine
sdk_dir = Path(".sdk")


def install_name_tool(*args):
    args_str = tuple(str(a) for a in args)
    subprocess.check_call(['install_name_tool', *args_str])


def recreate_sdk():
    if sdk_dir.is_dir():
        shutil.rmtree(str(sdk_dir))

    sdk_dir.mkdir()

    copy_rpr_sdk()
    copy_rif_sdk()


def find_file(path, glob):
    return next(f for f in path.glob(glob) if not f.is_symlink())


def copy_rpr_sdk():
    rpr_dir = Path("RadeonProRenderSDK/RadeonProRender")
    hip_dir = Path("RadeonProRenderSDK/hipbin")

    # creating rpr dir
    sdk_rpr_dir = sdk_dir / "rpr"
    sdk_rpr_dir.mkdir()

    # creating hipbin dir
    shutil.copytree(str(hip_dir), str(sdk_rpr_dir / "hipbin"))

    # copying inc files
    shutil.copytree(str(rpr_dir / "inc"), str(sdk_rpr_dir / "inc"))

    # copying rprTools files
    shutil.copytree(str(rpr_dir / "rprTools"), str(sdk_rpr_dir / "rprTools"))

    # copying bin lib files
    bin_glob = {
        'Windows': "binWin64/*.dll",
        'Linux': "binUbuntu18/*.so",
        'Darwin': "binMacOS/*.dylib"
    }[OS]

    sdk_bin_dir = sdk_rpr_dir / "bin"
    sdk_bin_dir.mkdir()

    for lib in rpr_dir.glob(bin_glob):
        shutil.copy(str(lib), str(sdk_bin_dir))

    if OS == 'Windows':
        # copying .lib files
        sdk_lib_dir = sdk_rpr_dir / "lib"
        sdk_lib_dir.mkdir()

        for lib in rpr_dir.glob("libWin64/*.lib"):
            shutil.copy(str(lib), str(sdk_lib_dir))


def copy_rif_sdk():
    rif_dir = Path("RadeonProImageProcessingSDK")

    # creating rpr dir
    sdk_rif_dir = sdk_dir / "rif"
    sdk_rif_dir.mkdir()

    # copying models
    shutil.copytree(str(rif_dir / "models"), str(sdk_rif_dir / "models"))

    # getting rif bin_dir
    if OS == 'Windows':
        os_str = "Windows"
    elif OS == 'Linux':
        os_str = "Ubuntu20"
    else:   # Darwin
        if PROC == 'x86_64':
            os_str = "OSX"
        else:
            os_str = "MacOS_ARM"
    bin_dir = rif_dir / os_str / "Dynamic"

    # copying inc files
    shutil.copytree(str(rif_dir / "include"), str(sdk_rif_dir / "inc"))

    # copying bin lib files
    sdk_bin_dir = sdk_rif_dir / "bin"
    sdk_bin_dir.mkdir()

    if OS == 'Windows':
        for lib in bin_dir.glob("*.dll"):
            shutil.copy(str(lib), str(sdk_bin_dir))

        # copying .lib files
        sdk_lib_dir = sdk_rif_dir / "lib"
        sdk_lib_dir.mkdir()

        for lib in bin_dir.glob("*.lib"):
            shutil.copy(str(lib), str(sdk_lib_dir))

    elif OS == 'Linux':
        shutil.copy(str(find_file(bin_dir, "libRadeonImageFilters.so*")),
                    str(sdk_bin_dir / "libRadeonImageFilters.so"))
        shutil.copy(str(find_file(bin_dir, "libRadeonML_MIOpen.so*")),
                    str(sdk_bin_dir / "libRadeonML_MIOpen.so"))
        shutil.copy(str(find_file(bin_dir, "libOpenImageDenoise.so*")),
                    str(sdk_bin_dir / "libOpenImageDenoise.so"))
        shutil.copy(str(find_file(bin_dir, "libMIOpen.so.2*")),
                    str(sdk_bin_dir / "libMIOpen.so.2"))
        shutil.copy(str(find_file(bin_dir, "libRadeonML.so.0*")),
                    str(sdk_bin_dir / "libRadeonML.so.0"))

    elif OS == 'Darwin':
        shutil.copy(str(find_file(bin_dir, "libRadeonImageFilters*.dylib")),
                    str(sdk_bin_dir / "libRadeonImageFilters.dylib"))
        if PROC == 'x86_64':
            shutil.copy(str(find_file(bin_dir, "libOpenImageDenoise*.dylib")),
                        str(sdk_bin_dir / "libOpenImageDenoise.dylib"))
        shutil.copy(str(find_file(bin_dir, "libRadeonML_MPS*.dylib")),
                    str(sdk_bin_dir / "libRadeonML_MPS.dylib"))
        shutil.copy(str(find_file(bin_dir, "libRadeonML.0*.dylib")),
                    str(sdk_bin_dir / "libRadeonML.0.dylib"))

        # adjusting id of RIF libs
        install_name_tool('-id', "@rpath/libRadeonImageFilters.dylib", sdk_bin_dir / "libRadeonImageFilters.dylib")
        if PROC == 'x86_64':
            install_name_tool('-id', "@rpath/libOpenImageDenoise.dylib", sdk_bin_dir / "libOpenImageDenoise.dylib")
        install_name_tool('-id', "@rpath/libRadeonML_MPS.dylib", sdk_bin_dir / "libRadeonML_MPS.dylib")
        install_name_tool('-id', "@rpath/libRadeonML.0.dylib", sdk_bin_dir / "libRadeonML.0.dylib")

    else:
        raise KeyError("Unsupported OS", OS)


if __name__ == "__main__":
    recreate_sdk()
