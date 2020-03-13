### Addon Run/Use Linux Ubuntu Requirements

- Ubuntu 18.04.03

- AMD drivers from web site
    // The instruction is here: http://support.amd.com/en-us/kb-articles/Pages/AMDGPU-PRO-Install.aspx 

- Blender 2.80 or later 
    
- Embree

    sudo apt-get install alien dpkg

    cd /tmp
    wget https://github.com/embree/embree/releases/download/v2.12.0/embree-2.12.0.x86_64.rpm.tar.gz
    tar xzvf ./embree-2.12.0.x86_64.rpm.tar.gz
    sudo alien embree-lib-2.12.0-1.x86_64.rpm
    sudo dpkg -i embree-lib_2.12.0-2_amd64.deb

- OpenImageIO

    sudo apt-get install libopenimageio1.6

- FreeImage
    sudo apt-get install libfreeimage-dev


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


### Build Requirements

	sudo apt-get install  \
		build-essential cmake python3-dev python3-pip \
		makeself patchelf \
		libpci-dev libdrm-dev opencl-headers

	pip3 install numpy cffi imageio

	// The pytest-v must be more then 3.0 it can be checked calling next command: pip3 show pytest


### Build

- Build the pyrpr and RPRHelper

python3 build.py

- run addon from source
export LD_LIBRARY_PATH=/usr/lib64
python3 tests/commandline/run_blender.py ~/blender/blender-2.78c-linux-glibc219-x86_64/blender tests/commandline/test_rpr.py
// In the middle should be your path to Blender's executable file.

- make addon installer
python3 build_zip_installer.py --target linux
//this will make .zip that can be installed with Blender(User Preferences/Addons/InstallFromFile)
