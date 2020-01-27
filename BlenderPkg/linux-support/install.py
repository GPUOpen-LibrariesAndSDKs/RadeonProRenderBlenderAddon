#!/usr/bin/python3
import os
import platform
import shutil
import subprocess
import traceback
from contextlib import contextmanager
from pathlib import Path

import sys
import argparse
import logging


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        log_error(message)
        parser.print_help()
        sys.exit(-1)


parser = ArgumentParser()
parser.add_argument('blender_path', help="Blender distro folder")

# debugging options
parser.add_argument('--no-matlib', action='store_true',
                    help="Install material library")
parser.add_argument('-v', '--verbose', action='store_true',
                    help="print debug info")
parser.add_argument('--log-file', default=None, help="save log to file")
parser.add_argument('--distr-dir', default='.',
                    help="location for unpacked distributiion")

home = Path.home()


def get_data_home():
    return Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))


def get_documents_dir():
    return Path(os.environ.get('XDG_DOCUMENTS_DIR', home / 'Documents'))


red = '\033[1;31m'
green = '\033[1;32m'
yellow = '\033[1;33m'
blue = '\033[0;34m'
default = '\033[0m'


class ColoredFormatter(logging.Formatter):
    def format(self, record):
        formatted = super().format(record)
        if record.levelno >= logging.ERROR:
            formatted = red + formatted + default
        elif record.levelno >= logging.WARNING:
            formatted = yellow + formatted + default
        elif record.levelno >= logging.INFO:
            formatted = green + formatted + default
        return formatted


console = logging.StreamHandler(stream=sys.stdout)
console.setFormatter(ColoredFormatter())
console.setLevel(logging.INFO)

logger = logging.getLogger()
logger.addHandler(console)
logger.setLevel(logging.DEBUG)


def set_log_file(log_path):
    file_handler = logging.FileHandler(filename=str(log_path), mode='w',
                                       encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s %(name)s : %(levelname)s %(message)s'))
    logger.addHandler(file_handler)


def log_debug(msg, *args):
    logging.debug(msg, *args)


def log_warning(msg, *args):
    logging.warning(msg, *args)


def log_info(msg, *args):
    logging.info(msg, *args)


def log_error(msg, *args):
    logging.error(msg, *args)


def log_install_stage(name):
    log_info("Installing %s ...", name)


def fatal_error(msg, *args):
    logging.error(msg, *args)
    sys.exit(-1)


def test_logging():
    print('test_logging...')

    log_path = 'test_logger.log'

    set_log_file(log_path)

    log_error("an error message")
    log_info("an info message")
    log_warning("a warning message")
    log_debug("a debug message")
    log_install_stage("a component")
    print('test_logging done')
    sys.exit(0)


# test_logging()

@contextmanager
def install_component(name):
    log_install_stage(name)
    try:
        yield
        log_info("..installing %s ok", name)
    except SystemExit as e:
        raise
    except:
        log_error("Error:\n %s", traceback.format_exc())
        fatal_error("Installing '%s' failed! ", name)

@contextmanager
def install_stage(name):
    log_info(name)
    try:
        yield
        log_info("...done")
    except SystemExit as e:
        raise
    except:
        log_error("Error:\n %s", traceback.format_exc())
        fatal_error("'%s' failed! ", name)


# https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
install_dir_for_files = get_data_home() / 'rprblender'
install_dir_for_material_library = get_documents_dir() / 'Radeon ProRender/Blender/Material Library'
install_dir_for_logs = install_dir_for_files

registered_token_path = (install_dir_for_files / '.registered')

if install_dir_for_files.exists():
    shutil.rmtree(str(install_dir_for_files))

args = parser.parse_args()

if args.log_file:
    set_log_file(args.log_file)
if args.verbose:
    console.setLevel(logging.DEBUG)

distr_dir = Path(args.distr_dir)

log_info('Installing to %s', install_dir_for_files)
install_dir_for_files.mkdir()

blender_executable_path = Path(args.blender_path) / 'blender'
if not blender_executable_path.is_file():
    parser.error("Blender executable not found in '%s'" % args.blender_path)

# # Required packages.
# packageEmbree='embree-lib-2.12.0'
# packageOpenImageIO='OpenImageIO-1.2.3'
#

with install_stage("Retrieving Blender version"):
    blender_version = ''
    try:
        output = subprocess.check_output(
            [str(blender_executable_path), '--version'])
        for line in output.decode('utf8').splitlines():
            if not blender_version and line.startswith('Blender'):
                blender_version = line.split(maxsplit=1)[1]
            if 'build hash:' in line:
                blender_version += "_%s" % line.split('build hash:')[1]
                break
    except subprocess.CalledProcessError as e:
        log_warning("Failed retrieving Blender version.\n %s \n %s",
                    e, e.output)

with install_stage("Checking HW configuration version"):
    checker = distr_dir / 'addon' / 'checker'
    subprocess.check_call([str(checker)], env={'BLENDER_VERSION': blender_version})


with registered_token_path.open('w'):
    pass

with install_stage("Checking os version"):
    os_expected = {'ID': 'Ubuntu', 'RELEASE': '18.03'}

    try:
        import lsb_release

        os_info = lsb_release.get_distro_information()
        log_debug("lsb_release.get_distro_information: %s", os_info)
        os_compatible = os_expected['ID'] == os_info['ID'] and \
                        os_info['RELEASE'] >= os_expected['RELEASE']

    except ImportError:
        os_compatible = False
        log_debug("Can't determine os compatibility for %s", platform.platform())

    if not os_compatible:
        print(red +
              "This product is built for {ID} {RELEASE}"
              " - you may encounter errors. Do you wish to continue?".format(
                  **os_expected)
              )
        while True:
            a = input(red + "(y or n)").lower()

            if 'y' == a:
                break
            if 'n' == a:
                log_warning('exiting...')
                sys.exit()

log_install_stage("Radeon ProRender for Blender")

print("Radeon ProRender for Blender EULA")
subprocess.check_call(['less', '-e', str(distr_dir / 'eula.txt')])

while True:
    a = input("Do you accept the agreement? (y or n)").lower()

    if 'y' == a:
        break
    if 'n' == a:
        log_warning('exiting...')
        sys.exit()
    print("Please answer yes or no.")


def package_is_installed(package_name):
    log_debug("Checking if '%s' already installed", package_name)
    try:
        cmd = ['dpkg', '-l', package_name]
        log_debug("executing: '%s'", cmd)
        text = subprocess.check_output(cmd).decode('utf8')
        for line in text.splitlines():
            if line.startswith('ii '):
                linesplit = line.split(maxsplit=2)[1]
                if package_name == line.split(maxsplit=2)[1] or linesplit.startswith(package_name):
                    return True
        log_debug("Package '%s' not listed in '%s'", package_name, text)
        return False
    except subprocess.CalledProcessError:
        log_debug("Can't find '%s'\n%s", package_name, traceback.format_exc())
        return False


def install_package(package_name):
    if package_is_installed(package_name):
        log_debug("'%s' already installed, good", package_name)
        return False
    else:
        with install_component(package_name):
            cmd = ['sudo', 'apt-get', 'install', package_name]
            log_debug(cmd)
            subprocess.check_call(cmd)
        return True

with install_component("Dependencies"):
    # install_package('libopenimageio1.6')
    install_package('libfreeimage3')
    amdopt=Path("/opt/amdgpu")
    if amdopt.exists():
        if install_package('libgl1-amdgpu-mesa-dev'): 
            cmd = ['sudo', 'ldconfig']
            subprocess.check_call(cmd)

with install_component("Addon Files"):
    log_debug("from '%s' to '%s'", os.getcwd(), install_dir_for_files)
    shutil.copytree(str(distr_dir / 'addon'), str(install_dir_for_files / 'addon'))
    shutil.copy(str(distr_dir / 'uninstall.py'), str(install_dir_for_files))
    with (install_dir_for_files / '.files_installed').open('w'):
        pass

with install_stage("Trying to remove previously installed Blender addon..."):
    try:
        remove_blender_addon = install_dir_for_files / 'addon' / 'remove_blender_addon.py'
        subprocess.check_output([
            str(blender_executable_path), '--background',
            '--python', str(remove_blender_addon)],
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        log_warning("Failed removing addon from Blender.\n %s \n %s",
                    e, e.output)

with install_component("addon to Blender"):
    install_addon_lines = [
        "import bpy",
        "from pathlib import Path",
        "bpy.ops.preferences.addon_install(overwrite=True, filepath=r'%s')" % str(
            install_dir_for_files / 'addon' / 'addon.zip'),
        "bpy.ops.preferences.addon_enable(module='rprblender')",
        "bpy.ops.wm.save_userpref()",
    ]

    install_to_blender = install_dir_for_files / 'addon' / 'install_blender_addon.py'

    with install_to_blender.open(mode='w') as f:
        for line in install_addon_lines:
            print(line, file=f)

    install_blender_addon_cmd = [str(blender_executable_path), '--background',
                                 '--python', str(install_to_blender)]
    log_debug("cmd: '%s'", install_blender_addon_cmd)

    try:
        subprocess.check_output(install_blender_addon_cmd, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        log_warning("Blender ouput: %s", e.output.decode('utf8'))
        raise

    with (install_dir_for_files / 'addon' / '.installed').open('w'):
        pass

matlib_skip = False
if args.no_matlib:
    matlib_skip = True
else:
    if install_dir_for_material_library.exists():
        while True:
            a = input(
                "Found installed material library at '%s', replace? (y or n)"
                % str(install_dir_for_material_library)).lower()

            if 'y' == a:
                shutil.rmtree(str(install_dir_for_material_library))
                matlib_skip = False
                break
            if 'n' == a:
                matlib_skip = True
                break
            print("Please answer yes or no.")

if not matlib_skip:
    with install_component("Material Library"):

        shutil.copytree(str(distr_dir / 'matlib/feature_MaterialLibrary'),
                        str(install_dir_for_material_library))

        with (install_dir_for_files / '.matlib_installed').open('w') as f:
            print(str(install_dir_for_material_library), file=f, end='')

log_info("Installation complete.")
log_warning("To uninstall, please run '%s/uninstall.py %s'",
            str(install_dir_for_files), str(args.blender_path))
