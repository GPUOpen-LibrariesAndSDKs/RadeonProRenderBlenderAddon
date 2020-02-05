import sys
import os
import subprocess
import shutil
import datetime
import errno
import re
import create_build_output

# Prevent pyc files from being generated.
sys.dont_write_bytecode = True

sOutputDir = "./out/_pb/"
sSystemFolder = os.path.join(sOutputDir, "system")


###############################################################################
# 
def RemoveDirs(sDir):
    try:
        sList = os.listdir(sDir)
    except OSError:
        os.remove(sDir)
        return

    for next_dir in sList:
        s = sDir + "/" + next_dir
        RemoveDirs(s)

    os.rmdir(sDir)


###################################################################
# update version, create build_output, build installer
def BuildInstaller():
    global sLogDir

    # clear folder and create structure
    if os.path.exists(sOutputDir) == True:
        print('Removing folder %s' % sOutputDir)
        RemoveDirs(sOutputDir);

    os.makedirs(sOutputDir)

    sLogDir = os.path.join(sSystemFolder, "PluginInstaller/logs/")

    if os.path.exists(sLogDir) == True:
        RemoveDirs(sLogDir)

    os.makedirs(sLogDir)

    # get version
    sPluginVersion, sPluginVersionParts = create_build_output.ReadAddOnVersion()

    create_build_output.create_zip_addon('addon.zip', sPluginVersion)

    # create the output structure
    sBuildOutputFolder = os.path.join(sSystemFolder, "build_output")
    create_build_output.CreateAddOnModule(sPluginVersion, sBuildOutputFolder)


###################################################################
# 
BuildInstaller()
