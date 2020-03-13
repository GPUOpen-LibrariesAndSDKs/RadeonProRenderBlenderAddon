### Addon Build/Run OSX Requirements

The Radeon ProRender Blender addon is a Python wrapper around a C++ core and
has some specific requirements.

### Prerequisites:

- The High Sierra OS 10.13.3 or later is required
    - We only use the Metal code path for this addon and this is the reason for this requirement
- Install Xcode
    - SDKROOT should be set in your .profile:
        - export SDKROOT="/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.13.sdk"
- Install Homebrew first and then the prerequisites by executing the following:
	- ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
	- /usr/local/bin/brew install homebrew/science/openimageio # Need 1.7
		- We built this library by hand so this step may not be needed any more
	- /usr/local/bin/brew install glew
	- /usr/local/bin/brew install castxml

	- Additionally Python 3.7 is required for compatibility with Blender. Install this
	version of Python and make sure that it comes first in the path when running the 
	build. On OSX, Python 2.7 is supplied in /usr/bin/python, it is not sufficient
	for building the Blender Radeon ProRender Addon.
	- Configure python3:
		- python3 -m pip install cffi # python-cffi
		- python3 -m pip install imageio
		- python3 -m pip install numpy
		- python3 -m pip install pyopengl


### ThirdParty libraries

There is ThirdParty repository included to the project as a submodule. Please update submodules:

Plugin includes 4 submodules:
RadeonProRender SDK:
git@github.com:Radeon-Pro/RadeonProRenderSDK.git

Shared components
Image Processing Library:
git@github.com:Radeon-Pro/RadeonProImageProcessingSDK.git

ThirdParty components and miscellaneous tools
git@github.com:Radeon-Pro/RadeonProRenderThirdPartyComponents.git

All of them are included via SSH protocol. You will need to create and install SSH keys https://help.github.com/en/github/authenticating-to-github/connecting-to-github-with-ssh

Once SSH keys are installed update/checkout submodules for active branch

` git submodule update --init -f --recursive`


### Building

- After syncing the source, run:
	- ./build_osx.sh

NOTES:
1. castxml will be required as the Python bindings are rebuilt everytime.

### Running

Ensure that the BLENDER_28X_EXE environment variable is set.  For example, add the following to
your ~/.profile with the correct path to the Blender executable:

    export BLENDER_28X_EXE="/Users/amd/Downloads/blender-2.78c-OSX_10.6-x86_64/blender.app/Contents/MacOS/blender"

To run the local build, use:
	- ./run_blender_with_rpr_osx.sh

If  you have run the .dmg based installer then there is a good chance that running Blender will pick
up the installed addon rather than the one with your local changes.  It is best to uninstall the addon or rename
the directory of the installed addon to ensure that you get the version under development. Here are some notes:
- the installed addon is located at ~/Library/Application Support/Blender/scripts/addons/rprblender
- rename this directory so that it does not get in the way of using the local code

If you need the material library in your local testing then install the addon using the .dmg and then do the 
renaming in the above step.  The material library is located at:
	- /Users/Shared/RadeonProRender/Blender/matlib

If you try to run a build and it exits almost right away then there is a good chance that the addon source
has been updated for a new Core but the Third Party components has not.  A mismatched version number can
cause this.  In this case, go through the steps to sync the ThirdParty repo and copy into the ThirdParty
directory on the addon source.

### Debugging

During development, changes can be introduced which cause the addon not to start up.  This often produces
continuous error messages on a timed event which makes figuring out what happened difficult.  Search
for the text "Any issues with DLLs seem to show up here." and uncomment the exit line below as this will
cause the addon to stop and show the error right away.

Blender can be started up under a debugger by using the following command:

./run_blender_with_rpr_osx.sh lldb

The startup arguments for Blender are passed to lldb so type "run" and hit return to start the debugger.

### Technical Notes:
1. The Blender OSX build puts the required dynamic libraries into /Users/Shared/RadeonProRender/lib. This
path is shared with the Maya RadeonProRender OSX plugin.

2. Searching within the directories with grep can be made easier with the following bash function:

blgrep() {
    grep -r $1 * --exclude-dir .build --exclude-dir dist
}

You can place this into your ~/.profile and then invoke searches such as: blgrep ObjectDelete  when in the top level directory of the plugin.


