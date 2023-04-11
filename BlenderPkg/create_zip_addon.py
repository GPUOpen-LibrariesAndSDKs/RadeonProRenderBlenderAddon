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

import zipfile
import zlib
import platform
from pathlib import Path
import subprocess
import shutil
import re


OS = platform.system()

repo_dir = Path("..")


def enumerate_addon_data():
    # copy pyrpr files
    pyrpr_dir = repo_dir / 'src/bindings/pyrpr'

    for f in pyrpr_dir.glob("src/*.py"):
        yield f, f.name

    for f in pyrpr_dir.glob(".build/*"):
        if f.is_file() and f.suffix != ".cpp":
            yield f, f.name

    # copy RPRBlenderHelper files
    rprblenderhelper_dir = repo_dir / "RPRBlenderHelper/.build"
    if OS == 'Windows':
        rprblenderhelper_dir /= "Release"

    for f in rprblenderhelper_dir.glob("*"):
        if f.suffix in (".dll", ".so", ".dylib"):
            yield f, f.name

    # copy addon python code
    rprblender_dir = repo_dir / "src/rprblender"
    for f in rprblender_dir.glob("**/*"):
        if not f.is_file() or f.name in ("configdev.py", "rprblender.log"):
            continue

        if f.name.endswith('.py') or f.name in ('athena.bin', 'EULA.html'):
            yield f, f.relative_to(rprblender_dir)

    # copying Core libs
    for lib in (repo_dir / ".sdk/rpr/bin").glob("*"):
        yield lib, lib.name

    # copying RIF libs
    for lib in (repo_dir / ".sdk/rif/bin").glob("*"):
        yield lib, lib.name

    # copy ML denoiser model data
    models_dir = repo_dir / ".sdk/rif/models"
    for f in models_dir.glob("**/*"):
        if f.is_file():
            yield f, Path("data/models") / f.relative_to(models_dir)


def get_version():
    # getting buid version
    build_ver = subprocess.getoutput("git rev-parse --short HEAD")

    # getting plugin version
    text = (repo_dir / "src/rprblender/__init__.py").read_text()
    m = re.search(r'"version": \((\d+), (\d+), (\d+)\)', text)
    plugin_ver = m.group(1), m.group(2), m.group(3)

    return (*plugin_ver, build_ver)


def create_zip_addon(build_dir):
    """ Pack addon files to zip archive """
    ver = get_version()

    zip_addon = build_dir / f"rprblender-{ver[0]}.{ver[1]}.{ver[2]}-{ver[3]}-{OS.lower()}.zip"

    print(f"Compressing addon files to: {zip_addon}")
    with zipfile.ZipFile(zip_addon, 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=zlib.Z_BEST_COMPRESSION) as myzip:
        for src, package_path in enumerate_addon_data():
            print(f"adding {src} --> {package_path}")

            arcname = str(Path('rprblender') / package_path)

            if str(package_path) == "__init__.py":
                print(f"    set version_build={ver[3]}")
                text = src.read_text()
                text = text.replace('version_build = ""', f'version_build = "{ver[3]}"')
                myzip.writestr(arcname, text)
                continue

            myzip.write(str(src), arcname=arcname)

    return zip_addon


def main():
    build_dir = Path(".build")
    if build_dir.is_dir():
        shutil.rmtree(build_dir)
    build_dir.mkdir()

    zip_addon = create_zip_addon(build_dir)
    print(f"Addon was compressed to: {zip_addon}")


if __name__ == "__main__":
    main()