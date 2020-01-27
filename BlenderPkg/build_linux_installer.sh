#!/usr/bin/env bash
rm -rf __pycache__

rm ThirdParty
ln -s ../ThirdParty ThirdParty

pushd ../

python3.7 build.py 

popd

python3.7 build_linux_installer.py

rm ThirdParty

