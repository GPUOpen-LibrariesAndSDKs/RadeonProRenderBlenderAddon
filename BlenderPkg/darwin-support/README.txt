Installation
============

There are 4 files in the Radeon ProRender Blender addon installer image:
- The RadeonProRenderAdddon-installer-<version>.pkg
- postinstall
- uninstall
- README.txt

NOTE: <version> is used to represent a part of a file name that may change such as "1.5.0".

If you were an early tester of this addon, please see the note below on cleaning up the original version.

The following steps will setup the addon for Blender:
- Open the .pkg file and install the required files on disk by following it steps
- Open the postinstall application to connect the addon to Blender

Use the uninstall application to remove the addon at a later time.

Both the postinstall and uninstall applications will prompt for the path to the Blender distribution so that a script can be run to connect or disconnect the addon from Blender.

Directories
===========

Running the install .pkg will place files into the following directory:
- /Users/Shared/RadeonProRender/Blender/

If run succesfully, the postinstall application will install the addon into:
- ~/Library/Application\ Support/Blender/<version>/scripts/addons/

Early Testers of Addon
======================

The installation directories for this addon has changed during its development.  If you were an early tester of this addon then you should remove the following directories before installing:
- ~/Library/Application\ Support/Blender/2.78/scripts/addons/rprblender
- ~/Documents/RadeonProRender/Blender
- /Users/Shared/RadeonProRender/lib
- /Users/amd/.local/share/rprblender


