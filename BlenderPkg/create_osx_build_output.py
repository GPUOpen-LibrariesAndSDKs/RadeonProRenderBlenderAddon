#!python3

import sys
import os
import platform
import subprocess
import datetime
import shutil
import errno
import re
import tempfile
import zipfile
import io

from pathlib import Path

materialLibraryXML = "../MaterialLibrary/2.0/xml_catalog_output"
materialLibraryMaps = "../MaterialLibrary/2.0/Maps"

repo_root = Path('..')

def repo_root_pushd():
    os.chdir(str(repo_root))
	
def repo_root_popd():
    os.chdir("BlenderPkg")

def Copy(src, dest):
    try:
        shutil.copytree(src, dest)
    except OSError as e:
        # If the error was caused because the source wasn't a directory
        if e.errno == errno.ENOTDIR:
            shutil.copy(src, dest)
        else:
            raise NameError('Directory not copied. Error: %s' % e)


if platform.system() in ("Linux","Darwin"):
    import pwd

    def get_user_name():
        return pwd.getpwuid(os.getuid())[0]
else:
    def get_user_name():
        return os.getlogin()


def enumerate_addon_data(version, target):
    pyrpr_path = repo_root / 'src/bindings/pyrpr'

    repo_root_pushd()
	
    git_commit = subprocess.check_output('git rev-parse HEAD'.split())
    git_tag = subprocess.check_output('git describe --always --tags --match builds/*'.split())
		
    repo_root_popd()

    version_text = """version=%r
git_commit=%s
git_tag=%s
user=%s
timestamp=%s
target=%s
    """%(
        version,
        repr(git_commit.strip().decode('utf-8')),
        repr(git_tag.strip().decode('utf-8')),
        repr(get_user_name()),
        tuple(datetime.datetime.now().timetuple()),
        repr(target)
        )
    yield version_text.encode('utf-8'), 'version.py'

    #test version a bit
    version_dict = {}
    exec(version_text, {}, version_dict)
    assert version == version_dict['version']

    rprsdk_bin = repo_root / '.sdk/rpr/bin'
    for name in os.listdir((str(rprsdk_bin))):
        yield Path(rprsdk_bin)/name, name

    name_ending = ""
    rifsdk_bin = repo_root / '.sdk/rif/bin'
    name_ending = ".dylib"
    for name in os.listdir((str(rifsdk_bin))):
        if name.endswith(name_ending):
            yield Path(rifsdk_bin)/name, name

    # copy pyrpr files
    pyrpr_folders = [pyrpr_path/'.build', pyrpr_path/'src']
    for pyrpr_folder in pyrpr_folders:
        for root, dirs, names in os.walk(str(pyrpr_folder)):
            for name in names:
                if any(ext in Path(name).suffixes for ext in ['.py', '.pyd', '.json']):
                    yield Path(root)/name, Path(root).relative_to(pyrpr_folder)/name

    # copy RPRBlenderHelper files
    rprblenderhelper_folder = repo_root / 'RPRBlenderHelper/.build'
    rprblenderhelper_files = ['libRPRBlenderHelper.dylib']

    for name in rprblenderhelper_files:
        root = rprblenderhelper_folder
        yield Path(root)/name, name

    # copy bindings files
    rprbindings_folder = repo_root / 'src/bindings/pyrpr/.build'
    rprbindings_files = ['_cffi_backend.cpython-37m-darwin.so']
    
    for name in rprbindings_files:
        root = rprbindings_folder
        yield Path(root)/name, name
    
    # copy addon python code
    rprblender_root = str(repo_root / 'src/rprblender')
    for root, dirs, names in os.walk(rprblender_root):
        for name in names:
            if name.endswith(('.py', '.bin')) and name != 'configdev.py':
                yield Path(root)/name, Path(root).relative_to(rprblender_root)/name

    # copy other files
    rprblender_root = str(repo_root / 'src/rprblender')
    for root, dirs, names in os.walk(rprblender_root):
        for name in names:
            if name == 'EULA.html':
                yield Path(root)/name, Path(root).relative_to(rprblender_root)/name
            elif name in ['RadeonProRender_ci.dat', 'RadeonProRender_co.dat', 'RadeonProRender_cs.dat']:
                yield Path(root)/name, Path(root).relative_to(rprblender_root)/name


def CreateAddOnModule(addOnVersion, build_output_folder):
    sys.dont_write_bytecode = True

    print('Creating build_output for AddOn version: %s' % addOnVersion)
    
    commit = subprocess.check_output(['git', 'describe', '--always'])

    build_output_rpblender = os.path.join(build_output_folder, 'rprblender')
    if os.access(build_output_rpblender, os.F_OK):
        shutil.rmtree(build_output_rpblender)

    os.makedirs(build_output_rpblender, 0x777)

    dst_fpath = build_output_rpblender + '/addon.zip'
    print('dst_fpath: ', dst_fpath)
    shutil.copy2('./addon.zip', dst_fpath)


def ReadAddOnVersion() :
    print("ReadAddOnVersion...")

    pyInitFileName = repo_root / 'src/rprblender/__init__.py'
    result = None
    with open( str(pyInitFileName), "r" ) as pyFile:
        s = pyFile.read()
    
        val = re.match( "(?s).*\"version\":\s\(([^)]+)\),", s )
        if val == None :
            raise NameError("Can't get addOnVersion")
    
        version = val.group(1)
        versionParts = version.split(",")
        if(len(versionParts) != 3):
            raise NameError("Invalid version string in __init__.py")
    
        sPluginVersionMajor = versionParts[0].rstrip().lstrip()
        sPluginVersionMinor = versionParts[1].rstrip().lstrip()
        sPluginVersionBuild = versionParts[2].rstrip().lstrip()
    
        sPluginVersion = sPluginVersionMajor + "." + sPluginVersionMinor + "." + sPluginVersionBuild

        result = sPluginVersion, (sPluginVersionMajor, sPluginVersionMinor, sPluginVersionBuild)  
    
        print( "  addOnVersion: \"%s\"" % sPluginVersion)
    
        print("ReadAddOnVersion ok.")
    return result


def create_zip_addon(package_name, version, target='windows'):

    with zipfile.ZipFile(package_name, 'w') as myzip:
        for src, package_path in enumerate_addon_data(version, target=target):
            if isinstance(src, bytes):
                myzip.writestr(str(Path('rprblender') / package_path), src)
            else:
                print('  file', src)
                myzip.write(str(src), arcname=str(Path('rprblender') / package_path))


def enumerate_lib_data():
    name_ending = ".dylib"
    rprsdk_bin = repo_root / '.sdk/rpr/bin'
    for name in os.listdir((str(rprsdk_bin))):
        if name.endswith(name_ending):
            yield Path(rprsdk_bin)/name, name
    
    rpipsdk_bin = next(repo_root.glob('.sdk/rif/bin'))
    for name in os.listdir((str(rpipsdk_bin))):
        if name.endswith(name_ending):
            yield Path(rpipsdk_bin)/name, name


def copy_libs(libpath):
    for src, package_path in enumerate_lib_data():
        lpath = libpath / package_path
        print("copy libs %s %s" % (src, lpath))
        shutil.copy(str(src),str(lpath))
