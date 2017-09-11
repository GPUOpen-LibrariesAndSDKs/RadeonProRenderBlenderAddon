#!/bin/bash

if [ -x "$BLENDER_EXE" ]; then

	rm -rf dist/
	mkdir dist
	cp -r "ThirdParty/RadeonProRender SDK/Linux-Ubuntu/lib" dist/
	cp ./RPRBlenderHelper/.build/libRPRBlenderHelper.so dist/lib

	ln -s dist/lib distlib 

	CDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	DIST_LIB="$CDIR/distlib"

	export LD_LIBRARY_PATH="$DIST_LIB"

	python3 tests/commandline/run_blender.py "$BLENDER_EXE" tests/commandline/test_rpr.py

	rm distlib

	exit

else

	echo "Could not file blender application"

fi

