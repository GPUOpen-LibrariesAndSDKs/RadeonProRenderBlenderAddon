### Addon Build/Run OSX Requirements

The Radeon ProRender Blender addon is a Python wrapper around a C++ core and
has some specific requirements.

Prerequisites:
--------------
- Install Xcode
- Install Homebrew first and then the prerequisites by executing the following:
	- ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
	- /usr/local/bin/brew install homebrew/science/openimageio # Need 1.7
		- We built this library by hand so this step may not be needed any more
	- /usr/local/bin/brew install glew
	- /usr/local/bin/brew install castxml

	- Additionally Python 3.5.2 is required for compatibility with Blender. Install this
	version of Python and make sure that it comes first in the path when running the 
	build.  On OSX, Python 2.7 is supplied in /usr/bin/python and it is not sufficient
	for building the Blender Radeon ProRender Addon.
	- Configure python3:
		- python3 -m pip install cffi # python-cffi
		- python3 -m pip install pytest
		- python3 -m pip install imageio
		- python3 -m pip install numpy
		- python3 -m pip install pyopengl

### Building
- After syncing the source, run:
	- ./build_osx.sh

NOTES:
1. This assumes that the private repository https://github.com/Radeon-Pro/RadeonProRenderThirdPartyComponents.git
 has been synced to a sibling directory of the Blender addon.
	- cd ThirdParty
	- ./unix_update.sh
	- cd ..

	NOTE: the two repositories are disconnected but must be kept in sync.

2. castxml will be required as the Python bindings are rebuilt everytime.

### Running
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

### Technical Notes:
1. The Blender OSX build puts the required dynamic libraries into /Users/Shared/RadeonProRender/lib. This
path is shared with the Maya RadeonProRender OSX plugin.
