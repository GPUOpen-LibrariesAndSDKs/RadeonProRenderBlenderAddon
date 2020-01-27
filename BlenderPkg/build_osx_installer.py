#/usr/bin/python3

import os
import stat
import sys
import argparse
import shutil
import subprocess
from pathlib import Path

import create_osx_build_output

parser = argparse.ArgumentParser()
parser.add_argument('--sign', action='store_true')
parser.add_argument('--nomatlib', action='store_true')

args = parser.parse_args()

signApp = args.sign
noMatLib = args.nomatlib

installer_build_dir = Path("./.installer_build")

if installer_build_dir.exists():
    shutil.rmtree(str(installer_build_dir))

buildInstallerApp = True

plugin_version, plugin_version_parts = create_osx_build_output.ReadAddOnVersion()
print("Version info: %s %s" % (plugin_version, plugin_version_parts))

# Need the following directories:
# dist/Blender/addon
# dist/Blender/libs
# dist/Blender/matlib
# dist/resources
# dist/scripts
# dist/pkg
# dist/bld
#
dist_dir = installer_build_dir / 'dist'
addon_files_dist_dir = dist_dir / 'Blender/addon'
addon_files_dist_dir.mkdir(parents=True)
libs_files_dist_dir = dist_dir / 'Blender/lib'
libs_files_dist_dir.mkdir(parents=True)
material_library_dist_dir = dist_dir / 'Blender/matlib'
resource_files_dist_dir = dist_dir / 'resources'
resource_files_dist_dir.mkdir(parents=True)
pkg_files_dist_dir = dist_dir / 'pkg'
pkg_files_dist_dir.mkdir(parents=True)
bld_files_dist_dir = dist_dir / 'bld'
bld_files_dist_dir.mkdir(parents=True)
scripts_files_dist_dir = dist_dir / 'scripts'
scripts_files_dist_dir.mkdir(parents=True)

if noMatLib:
	print("Not adding matlib\n")
else:
	create_osx_build_output.CreateMaterialLibrary(str(material_library_dist_dir))

support_path = Path('./darwin-support')
for name in ['welcome.html']:
    shutil.copy(str(support_path / name), str(resource_files_dist_dir))

legal_path = Path('../Legal')
for name in ['eula.txt']:
    shutil.copy(str(legal_path / name), str(resource_files_dist_dir))

for name in ['install_blender_addon.py', 'remove_blender_addon.py', 'postinstall', 'uninstall', 'blender_pip.py']:
    shutil.copy(str(support_path / name), str(addon_files_dist_dir))

if buildInstallerApp:
    for name in ['README-INSTALLERAPP.txt']:
        shutil.copy(str(support_path / name), str(bld_files_dist_dir / "README.txt"))
else:
    for name in ['README.txt']:
        shutil.copy(str(support_path / name), str(bld_files_dist_dir / "README.txt"))

# Special case
for name in ['postinstall-checker']:
    shutil.copy(str(support_path / name), str(scripts_files_dist_dir) + str("/postinstall"))


# Build the checker

lib_path_hint = ''
checker_path = support_path / 'Checker'
checker_build_path = checker_path / '.build'
checker_build_path.mkdir(exist_ok=True)
subprocess.check_call(['cmake', '-DCMAKE_LIBRARY_PATH='+ lib_path_hint +'/lib/x86_64-darwin-gnu', '..'], cwd=str(checker_build_path))
subprocess.check_call(['make'], cwd=str(checker_build_path))

for name in ['checker']:
    shutil.copy(str(support_path / "Checker/.build" / name), str(addon_files_dist_dir))

# Copy libraries

create_osx_build_output.copy_libs(libs_files_dist_dir)

# Create zip file

create_osx_build_output.create_zip_addon(str(libs_files_dist_dir),str(addon_files_dist_dir / 'addon.zip'),
                                         plugin_version, target='darwin')

# Create the RprBlender.plist file from the template using the version number

template_plist_file=Path("./RprBlenderTemplate.plist")
blender_plist_file=Path("./RprBlender.plist")

content=template_plist_file.read_text()
updated_content=content.replace("<VERSION>",plugin_version)
blender_plist_file.write_text(updated_content)

# Build packages

buildDMG = True
debuggingOpenInstaller = False

pkg_name = '%s/RadeonProRenderAddon-%s.pkg' % (str(pkg_files_dist_dir),plugin_version)

if not buildInstallerApp:
    cmd = ['pkgbuild',
           '--identifier', 'com.amd.rpr.inst-blender.app',
           '--root', '.installer_build/dist/Blender',
           '--install-location', '/Users/Shared/RadeonProRender/Blender',
           '--scripts', '.installer_build/dist/scripts',
           pkg_name
        ]
else:
    cmd = ['pkgbuild',
           '--identifier', 'com.amd.rpr.inst-blender.app',
           '--root', '.installer_build/dist/Blender',
           '--install-location', '/Users/Shared/RadeonProRender/Blender',
           pkg_name
           ]
subprocess.check_call(cmd)

# productbuild --synthesize --package pkg_name .installer_build/RprBlender.plist
cmd = ['productbuild',
       '--synthesize',
       '--package', pkg_name,
       '.installer_build/RprBlender.plist'
       ]
subprocess.check_call(cmd)

if not buildInstallerApp:
    inst_name = '%s/RadeonProRenderAddon-installer-%s.pkg' % (str(bld_files_dist_dir),plugin_version)
    cmd = ['productbuild',
           '--distribution', 'RprBlender.plist',
           '--resources', '.installer_build/dist/resources',
           '--package-path', '.installer_build/dist/pkg',
           inst_name
           ]
    subprocess.check_call(cmd)

# Make the app(s)

def make_app(dirpath,scriptpath):
    sname = os.path.basename(scriptpath)
    sdir = os.path.dirname(scriptpath)
    app_path=os.path.join(dirpath,sname)
    app_script_dir=os.path.join(app_path+str(".app"),"Contents/MacOS")
    if not os.path.exists(app_script_dir):
        os.makedirs(app_script_dir)
    app_script_name = os.path.join(app_script_dir,str(sname))
    shutil.copy(scriptpath,app_script_name)

    state = os.stat(app_script_name)
    os.chmod(app_script_name,state.st_mode|stat.S_IEXEC)

info_plist_str = """<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>CFBundleDevelopmentRegion</key>
        <string>English</string>
        <key>CFBundleExecutable</key>
        <string><APPNAME></string>
        <key>CFBundleGetInfoString</key>
        <string>0.1.0, Copyright 2018 AMD</string>
        <key>CFBundleIconFile</key>
        <string><APPNAME>.icns</string>
        <key>CFBundleIdentifier</key>
        <string>com.amd.<APPNAME></string>
        <key>CFBundleDocumentTypes</key>
        <array>
        </array>
        <key>CFBundleInfoDictionaryVersion</key>
        <string>6.0</string>
        <key>CFBundlePackageType</key>
        <string>APPL</string>
        <key>CFBundleShortVersionString</key>
        <string>0.1.0</string>
        <key>CFBundleSignature</key>
        <string><APPSIGNATURE></string>
        <key>CFBundleVersion</key>
        <string>0.1.0</string>
        <key>NSHumanReadableCopyright</key>
        <string>Copyright 2018 AMD.</string>
        <key>LSMinimumSystemVersion</key>
        <string>10.13.3</string>
    </dict>
    </plist>
"""

trampoline_str = """#include <stdio.h>
#include <libgen.h>
#include <string.h>
#include <stdlib.h>
int main(int argc, const char *argv[])
{
	if (!argv[0]) return -1;
	char* argv0 = strdup(argv[0]);
	if (!argv0) return -1;
	char *dir_str = dirname(argv0);
	char sysbuf[1024];
	sprintf(sysbuf,"%s/../Resources/%s %s > /tmp/rpr.log",dir_str,"<APPNAME>",dir_str);
    printf("config %s %s %s\\n",argv0,dir_str,sysbuf);
	system(sysbuf);
	free(argv0);
	return 0;
}
"""

exe_str = """#!/bin/bash
dir="$1"
checker="$dir/../MacOS/checker"
postinstall="/Users/Shared/RadeonProRender/Blender/addon/postinstall"
uninstall="/Users/Shared/RadeonProRender/Blender/addon/uninstall"
pkg="$dir/../Packages/<PKGNAME>"

operation() {
osascript <<'END'
tell me to activate
set question to display dialog "A Radeon ProRender Blender install package has been found. Select from the following options:" buttons {"Install", "Uninstall"} default button 2
set answer to button returned of question
if answer is equal to "Install" then
return 0
end if
error number -1
END
}

moveinstalltotrash() {
osascript <<'END'
tell application "Finder"
set sourceFolder to POSIX file "/Users/Shared/RadeonProRender/Blender/"
delete sourceFolder  # move to trash
end tell
END
}

installdone(){
osascript <<END
tell me to activate
display dialog "Installed the Radeon ProRender addon." buttons { "OK" } default button 1
END
}

uninstalldone(){
osascript <<END
tell me to activate
display dialog "Uninstalled the Radeon ProRender addon." buttons { "OK" } default button 1
END
}

dist="/Users/Shared/RadeonProRender/Blender/"
if [ -d "$dist" ]
then
    operation
fi

if [ $? -eq 0 ]
then
    /System/Library/CoreServices/Installer.app/Contents/MacOS/Installer "$pkg"
    if [ -d "$dist" ]
    then
        "$postinstall"
        installdone
    fi
else
    "$uninstall"
    moveinstalltotrash
    uninstalldone
fi

"""

def make_installer_app(appName,appExe,dirpath,signing_str):
    icon_file = Path("../Icons/darwin//RadeonProRenderBlenderInstaller.icns")
    bundle_path=os.path.join(dirpath,appName+".app")
    contents_path=os.path.join(bundle_path,"Contents")
    for name in ['MacOS', 'Contents', 'Resources', 'Packages']:
        os.makedirs(os.path.join(contents_path,name))
    # Build and place the package into the app
    inst_name = '%s/RadeonProRenderAddon-installer-%s.pkg' % (os.path.join(contents_path,'Packages'),plugin_version)
    cmd = ['productbuild',
           '--distribution', 'RprBlender.plist',
           '--resources', '.installer_build/dist/resources',
           '--package-path', '.installer_build/dist/pkg',
           inst_name
           ]
    subprocess.check_call(cmd)
    # Copy files
    shutil.copy(str(icon_file),os.path.join(contents_path,'Resources'))
    shutil.copy(str(appExe),os.path.join(contents_path,'MacOS'))
    # Make the trampoline
    trampoline_cpp = os.path.join(str(installer_build_dir),"main.cpp")
    with open(trampoline_cpp,"w") as f:
        final_trampoline_str = trampoline_str.replace("<APPNAME>",appName)
        f.write(final_trampoline_str)
    cmd = [ 'clang', trampoline_cpp, '-o',  os.path.join(os.path.join(contents_path,'MacOS'),appName) ]
    subprocess.check_call(cmd)
    # Make the exe
    app_exe = os.path.join(os.path.join(contents_path,'Resources'),appName)
    with open(app_exe, "w") as f:
        final_exe_str = exe_str.replace("<PKGNAME>",os.path.basename(inst_name))
        f.write(final_exe_str)
    # Make exe executable
    state = os.stat(app_exe)
    os.chmod(app_exe,state.st_mode|stat.S_IEXEC)
    # Make the PkgInfo
    app_signature = "APPLRpBl"
    pkg_info = os.path.join(contents_path,'PkgInfo')
    with open(pkg_info, "w") as f:
        f.write(app_signature)
        f.write("\n")
    # Make the Info.plist
    info_plist = os.path.join(contents_path,'Info.plist')
    with open(info_plist, "w") as f:
        info_plist_str1 = info_plist_str.replace("<APPNAME>",appName)
        info_plist_str2 = info_plist_str1.replace("<APPSIGNATURE>",app_signature)
        f.write(info_plist_str2)
    # Sign if required
    # Check Gatekeeper conformance with: spctl -a -t exec -vv .installer_build/dist/bld/RadeonProRenderBlenderInstaller.app/
    if signing_str:
        # Sign the checker
        cmd = ['codesign', '--sign', signing_str, os.path.join(os.path.join(contents_path,'MacOS'),"checker") ]
        subprocess.check_call(cmd)
        # Sign the trampoline
        cmd = ['codesign', '--sign', signing_str, os.path.join(os.path.join(contents_path,'MacOS'),appName) ]
        subprocess.check_call(cmd)
        # Sign the app bundle
        cmd = ['codesign', '--sign', signing_str, bundle_path ]
        try:
            subprocess.check_call(cmd)
        except:
            print("Bundle may already be signed\n")

if not buildInstallerApp:
    make_app(str(bld_files_dist_dir),str(support_path / "postinstall"))
    make_app(str(bld_files_dist_dir),str(support_path / "uninstall"))
else:
    app_exe = "./darwin-support/Checker/.build/checker"
    signing_str = ""
    if signApp:
        signing_str = input("##### Enter the Developer ID:")
    make_installer_app("RadeonProRenderBlenderInstaller",app_exe,str(bld_files_dist_dir),signing_str)

# Create DMG

if buildDMG:
    dmg_name = '.installer_build/RadeonProRenderBlender_%s.dmg' % plugin_version
    cmd = ['hdiutil',
           'create',
           '-volname', 'RadeonProRenderBlender-%s' % plugin_version,
           '-srcfolder', str(bld_files_dist_dir),
           '-ov',
           dmg_name]
    subprocess.check_call(cmd)
    if debuggingOpenInstaller:
        os.system("open %s" % dmg_name)
else:
    if debuggingOpenInstaller:
        os.system("open %s" % inst_name)
