#!/usr/bin/python3
import argparse
import shutil
import subprocess
from pathlib import Path

import sys

# # Installer text colours.
red = '\033[1;31m'
blue = '\033[0;34m'
default = '\033[0m'


class ArgumentParser(argparse.ArgumentParser):

    def error(self, message):
        print(red+'Error:', message)
        parser.print_help()
        sys.exit(-1)


parser = ArgumentParser()
parser.add_argument('blender_path', help="Blender distro folder")
parser.add_argument('--install-dir', default=None, help="Blender install folder")
args = parser.parse_args()

blender_executable_path = Path(args.blender_path)/'blender'
if not blender_executable_path.is_file():
    parser.error("Blender executable not found in '%s'" % args.blender_path)

install_dir = Path(args.install_dir or Path(__file__).parent)

print(blue+"Removing Radeon ProRender for Blender"+default)

if not (install_dir / 'addon' / '.installed').is_file():
    print(blue+"Blender addon seems not installed, but will try to remove anyway..."+default)

print(blue+"Removing Blender addon..."+default)

remove_blender_addon = install_dir/'addon'/'remove_blender_addon.py'

if subprocess.call([str(blender_executable_path), '--background',
                    '--python', str(remove_blender_addon)]):
    print(red + "Failed removing addon from Blender. Please do it manually from User Preferences" + default)

if (install_dir/'.files_installed').is_file():
    print(blue + "Removing installed files..." + default)
    shutil.rmtree(str(install_dir))

print(blue+"Removal complete."+default)

