rm -rf __pycache__

rm ThirdParty
ln -s ../ThirdParty ThirdParty

pushd ../

python3.7 build.py

popd

# Parameters: --sign will prompt user for the signing id
python3.7 build_osx_installer.py --nomatlib $1

rm ThirdParty
