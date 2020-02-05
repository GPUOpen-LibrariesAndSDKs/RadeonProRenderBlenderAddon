#!/usr/bin/env bash
rm -rf __pycache__

pushd ..

./build.sh

popd

python3.7 build_linux_installer.py

