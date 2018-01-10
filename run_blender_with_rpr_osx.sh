#!/bin/bash

echo BLENDER_EXE "${BLENDER_EXE}"

if [ -x "${BLENDER_EXE}" ]; then

	rm -rf dist/
	mkdir dist
	cp -r "ThirdParty/RadeonProRender SDK/Mac/lib" dist/
	cp ./RPRBlenderHelper/.build/libRPRBlenderHelper.dylib dist/lib

	ln -s dist/lib distlib 

	CDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	DIST_LIB="$CDIR/distlib"

	export LD_LIBRARY_PATH="$DIST_LIB"

	python3 tests/commandline/run_blender.py "$BLENDER_EXE" tests/commandline/test_rpr.py

	rm distlib

	exit

else

	echo "Could not find blender application"

fi

