#!/bin/bash

set -e

RPR_SDK="ThirdParty/RadeonProRender SDK/Linux-Ubuntu"
IMAGE_FILTER_DIR="ThirdParty/RadeonProImageProcessing/Linux/Ubuntu"
IMAGE_FILTER_LIBNAME="libRadeonImageFilters64.so"

function pre_init()
{
	# Python scipts waiting, that all dynamic dependecies will be at RadeonSDK directory.
	# It is not well, as in future RPR can have more dynamic deps and they can be suitied in different
	# directories
	
	if [ ! -f "$RPR_SDK/lib/$IMAGE_FILTER_LIBNAME" ];
	then
		cp "$IMAGE_FILTER_DIR/lib64/$IMAGE_FILTER_LIBNAME" "$RPR_SDK/lib/$IMAGE_FILTER_LIBNAME"
	fi
}


if [ -x "$BLENDER_EXE" ]; then

	pre_init
	
	rm -rf dist/
	mkdir dist
	cp -r "ThirdParty/RadeonProRender SDK/Linux-Ubuntu/lib" dist/
	cp ./RPRBlenderHelper/.build/libRPRBlenderHelper.so dist/lib

	ln -s dist/lib distlib 

	CDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	DIST_LIB="$CDIR/distlib"

	export LD_LIBRARY_PATH="$DIST_LIB:$LD_LIBRARY_PATH"

	python3 tests/commandline/run_blender.py "$BLENDER_EXE" tests/commandline/test_rpr.py

#	rm distlib

	exit

else

	echo "Could not file blender application"

fi

