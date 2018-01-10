### Addon Build/Run OSX Requirements

The Radeon ProRender Blender addon is a Python wrapper around a C++ core and
has some specific requirements.

Prerequisites:
--------------
- Install Xcode
- Install Homebrew first and then the prerequisites by executing the following:
	- ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
	- /usr/local/bin/brew install homebrew/science/openimageio # Need 1.7
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
2. castxml will be required as the Python bindings are rebuilt everytime.

### Running
To run the local build, use:
	- ./run_blender_with_rpr_osx.sh

### Technical Notes:
1. The Blender OSX build puts the required dynamic libraries into /Users/Shared/RadeonProRender/lib. This
path is shared with the Maya RadeonProRender OSX plugin.
