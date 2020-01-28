rm -rf __pycache__

pushd ..

./build_osx.sh

popd

# Parameters: --sign will prompt user for the signing id
python3.7 build_osx_installer.py --nomatlib $1
