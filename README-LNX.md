# Development environment preparation

1. Ubuntu 22.04.04 LTS 
2. Update system (required for update amdgpu linux drivers)
```
apt-get update
apt-get upgrade
```
3. Download [amdgpu drivers for linux](https://www.amd.com/en/support/linux-drivers)
4. Install amdgpu deb package (it setup official repo + required script for futher gpu driver install)
```
apt install ./amdgpu-install_*.deb
```
5. Install amdgpu driver itself
```
amdgpu-install
```
6. Reboot (required for amdgpu driver init)
7. Download [blender 3.1](https://www.blender.org/download)
8. Unpack somewhere
9. Setup env. variable `BLENDER_EXE` and set to blender executable. For example:
```
echo "BLENDER_EXE=/home/feniks/bin/blender-4.1.0-linux-x64/blender" >> ~/.bashrc
```

10. Install blender build dependencies
```
sudo apt-get install castxml python3.11 python3.11-dev \
	build-essential cmake \
        makeself patchelf libpci-dev libdrm-dev opencl-headers \
        libopenimageio-dev libfreeimage-dev libembree-dev
```
11. Install python deps
```
python3.11 -m pip install numpy cffi imageio pytest
```
12. Add to PATH required python binaries. For example:
```
echo "PATH=/home/amd/.local/bin:$PATH" >> ~/.bashrc
```
13.  


# Project build

> [!NOTE]
> Dont forget to fetch project submodules  `git submodule update --init -f --recursive`

To build project run command
```
./build.sh
```

## Create shipment archive
To create shipment archive, please, run script:
```
cd BlenderPkg
./build.sh
```
Shipment package should be in  `BuildPkg/.build` directory. 

To install shipment build, run blender, select `Edit -> Preferences -> Addons -> Install`. 
Then activate "RadeonProRender"

# Run addon from source
```
export LD_LIBRARY_PATH=/usr/lib64
python3.11 tests/commandline/run_blender.py $BLENDER_EXE tests/commandline/test_rpr.py
// In the middle should be your path to Blender's executable file.
```

