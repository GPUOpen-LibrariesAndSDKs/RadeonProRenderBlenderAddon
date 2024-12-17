# Radeon ProRender Blender Addon

## Releases
- [4.1, 4.2, 4.3](https://github.com/GPUOpen-LibrariesAndSDKs/RadeonProRenderBlenderAddon/releases/tag/v3.6.11)
- [4.0](https://github.com/GPUOpen-LibrariesAndSDKs/RadeonProRenderBlenderAddon/releases/tag/v3.6.10)

For older Blender versions, see [releases](https://github.com/GPUOpen-LibrariesAndSDKs/RadeonProRenderBlenderAddon/releases). 

## Supported Devices 
- AMD GPUs (Vega, Navi 1x, Navi 2x, Navi 3x)
- NVIDIA GPUs
- Apple Mx GPUs
- AMD, Intel CPUs

## For Developers

### Build Requirements

- Blender 4.1+
- Python 3.11 (Blender 4.1 uses 3.11) x64(for Core) - all code, addon and misc tested with python3
- python-cffi
  - `py -3.11 -m pip install cffi`
  - `py -3.11 -m pip install numpy`
- Visual Studio 2015 SP3 / 2017 / 2019 with SDK 8.1 and 2015.3 v140 toolset installed
- If you are using Visual studio 2019 you would need to install the Windows SDK 8.1 manually from Microsoft website https://developer.microsoft.com/en-us/windows/downloads/sdk-archive/
- cmake 3.x. Make sure it's added to the PATH environment variable

Note that the .sln provided is for easy editing and searching of files on Windows.  The blender code builds on the command line rather than in the solution file.  Visual Studio does provided support for debugging Python when you attach to the running Blender process with loaded addon.

### Submodules

Plugin includes 4 submodules:
- RadeonProRender SDK
- Shared components
- Image Processing Library
- ThirdParty components and miscellaneous tools

Please update submodules:

```
git submodule update --init -f --recursive
```

## Developing

## Build

run `build.py` to build.

## Run Addon while developing it(without real installation)

- make sure you have no installed addon for Blender version you want to use; remove installed version if needed.
- set environment variable BLENDER_EXE to blender.exe you want to use via the command line or system environment settings.
- run run_blender_with_rpr.cmd

Example:

`set BLENDER_EXE="C:\Program Files\Blender Foundation\Blender 2.93\blender.exe" && run_blender_with_rpr.cmd`

### Coding Conventions

Aim is to conform to [pep8](https://www.python.org/dev/peps/pep-0008/). 
At minimum it's 4 spaces for indentation, sources are utf-8, there's .gitconfig in the root of the project - please set you editor to use it(for most simplicity). E.g. PyCharm(recommended!) default setting are fine and seems that it also picks up .editorconfig automatically also, Tortoise Merge has a checkbox 'Enable EditorConfig', for Visual Studio there's [EditorConfig extension](https://visualstudiogallery.msdn.microsoft.com/c8bccfe2-650c-4b42-bc5c-845e21f96328)

Git - we try to avoid merge commits, easiest way to do it:

`git config [--global] merge.ff only` # this one rejects merges that would result in merge commit
 
`git config [--global] pull.rebase true` # converts pull to do, essentially, fetch&rebase 

Also, make more meaningful commits(one commit per feature) the easy way: 

`git merge <branch> --squash` # this will create a single change set from multiple commits coming from `<branch>`

### Debugging

#### log

Using python's 'logging' module underneath, rprblender.utils.logging has functions similar to logging. It also includes callable class Log which provides simplified interface to do logging.
Example:
    from rprblender.utils import logging
    log = logging.Log(tag='export.mesh')

    log("sync", mesh, obj)

e.g. `logging.debug(*argv, tag)` where argv is what is printed(same as with print) and tag is string suffix for logger name, for filtering
so that `logging.limit_log(name, level_show_always)` will allow to filter out what doesn't start with `name`(expect levels equal or above `level_show_always`)

 configdev.py(loaded very early) can be used to include code like `limit_log` to configure your session

    from .utils import logging
    logging.limit_log('default', logging.DEBUG)
    
    from . import config
    config.pyrpr_log_calls = True #  log all Core function calls to console, can be VERY useful

- Visual Studio has really nice(and working) mixed(python and C stack) debugging - recommended! 
- Blender debug - it's easiest to [build Blender](https://wiki.blender.org/index.php/Dev:Doc/Building_Blender/Windows/msvc/CMake) in Release or RelWithDebInfo(and add ``#pragma optimize( "", off )``) 
- Debug in PyCharm - `import pydevd; pydevd.settrace('localhost', port=52128, stdoutToServer=True, stderrToServer=True, suspend=False)`

## Making a new release

- Move to `BlenderPkg` directory
- Run `build_osx-arm64.sh` for Mac for MX processors
- Tag the commit in the build folder's ProRenderBlenderPlugin `git tag builds/x.y.zz`
- Push the tag `git push --tags` 
- Increase version in `src/rprblender/__init__.py`

## PyCharm

### Blender api intellisense support

Get [pycharm-blender](https://github.com/mutantbob/pycharm-blender). See instructions on the github page or, in short, 
run `pypredef_gen.py` from Blender itself or using command line, e.g. `blender --python pypredef_gen.py`,
add "pypredef" folder path that this script creates to you PyCharm Interpreter paths, find paths settings under `File | Settings(or Default Settings) | Project Interpreter`
 
Increase max file size for Pycharm intellisence(bpy.py generated is huge), go to `Help | Edit Custom VM Options` and add the following line:

  -Didea.max.intellisense.filesize=5000000

Restart PyCharm

## Visual Studio

### Create and configure RPRBlender python project 

Install python extension in Visual Studio

Create new project from existing python code: Menu -> File -> New -> Project -> Python tab -> From Existing Python Code

Add following Search Paths to project:
  - rprblender\support
  - <path to Blender 2.93>\2.93\scripts\modules   # path where to Blender's modules
  - <path to "PyCharm->Blender api intellisense support">

### Configure VS remote debugger to Blender

#### Install Blender-VScode-Debugger addon

Get Blender-VScode-Debugger plugin for Blender from https://github.com/Barbarbarbarian/Blender-VScode-Debugger

Install plugin Blender_VScode_Debugger.py in Blender: Menu -> File -> User Preferences -> Click "Install Add-on from file" -> Select Blender_VScode_Debugger.py -> Click "Install Add-on from file". New adddon "Development: Debugger for Visual Code" should be appeared

Enable "Development: Debugger for Visual Code" addon. Select "Path to PTVSD module": C:\Program Files (x86)\Microsoft Visual Studio 14.0\Common7\IDE\Extensions\Microsoft\Python Tools for Visual Studio\2.2\

Click "Save User Settings"

#### Attach VS remote debugger to Blender

In Blender: press <Space> -> in appeared dialog type "debug" -> select "Connect to Visual Studio Code Debugger"

In VS: Menu -> Debug -> Attach To Process -> select Transport "Python remote (ptvsd)" -> type in Qualifier "my_secret@localhost:3000" -> click Refresh: process Blender.exe "tcp://localhost:3000" should be appeared -> select process -> click Attach

Remote debugging connection established.
 

### Versioning

The version number should be updated when a new plugin is released.  This is done by editing the version field
of the bl_info structure in the `src/rprblender/__init__.py` file. Currently a build script will update the build
number when checkins happen to the master branch.  So it is only necessary to update the major or minor number
when required.

