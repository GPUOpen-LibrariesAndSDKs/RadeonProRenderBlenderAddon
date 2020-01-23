#!/bin/bash

echo BLENDER_28x_EXE "${BLENDER_28x_EXE}"

DEBUGGER_EXE="$1"

if [ -x "${BLENDER_28x_EXE}" ]; then
	rm -rf dist/
	mkdir dist
	cp -r .sdk/rpr/bin dist/
	cp ./RPRBlenderHelper/.build/libRPRBlenderHelper.dylib dist/lib

	ln -s dist/lib distlib 

	CDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	DIST_LIB="$CDIR/distlib"

	export LD_LIBRARY_PATH="$DIST_LIB"

	python3 cmd_tools/run_blender.py "$BLENDER_28x_EXE" cmd_tools/test_rpr.py "$DEBUGGER_EXE"

	rm distlib

	exit

else

	echo "Could not find blender application"

fi

