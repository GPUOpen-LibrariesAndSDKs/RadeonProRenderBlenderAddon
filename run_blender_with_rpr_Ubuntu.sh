#!/bin/bash

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WORK_DIR=`mktemp -d -p /tmp rpr_blender_workdir_XXXXXXXX`

RPR_SDK="ThirdParty/RadeonProRender SDK/Linux-Ubuntu"
IMAGE_FILTER_DIR="ThirdParty/RadeonProImageProcessing/Linux/Ubuntu"
IMAGE_FILTER_LIBNAME="libRadeonImageFilters64.so"
GLTF_DIR="ThirdParty/RadeonProRender-GLTF/Linux-Ubuntu/lib"
GLTF_LIBNAME="libProRenderGLTF.so"


function init()
{
	if [ ! -x "$BLENDER_EXE" ]; then
		echo "Could not find blender application. Please, specify BLENDER_EXE environment variable"
		exit 1
	fi

	if [[ ! "$WORK_DIR" || ! -d "$WORK_DIR" ]]; then
		echo "Could not create work dir $WORK_DIR"
		exit 2
	fi

	# link rpr libs to workdir
	for f in "$DIR/$RPR_SDK/lib/"*.so; do
		ln -s "$f" "$WORK_DIR/"
	done
	# link imageprocessing lib to workdir
	ln -s "$DIR/$IMAGE_FILTER_DIR/lib64/$IMAGE_FILTER_LIBNAME" "$WORK_DIR/"

	# link gltf lib to workdir
	ln -s "$DIR/$GLTF_DIR/$GLTF_LIBNAME" "$WORK_DIR/"

	# link helper to workdir
	ln -s "$DIR/RPRBlenderHelper/.build/libRPRBlenderHelper.so" "$WORK_DIR/"
}

# deletes the work directory
function cleanup {      
	rm -rf "$WORK_DIR"
}

# register the cleanup function to be called on the EXIT signal
trap cleanup EXIT

function main() 
{
	init

	export LD_LIBRARY_PATH="$WORK_DIR:$LD_LIBRARY_PATH"

	python3 tests/commandline/run_blender.py "$BLENDER_EXE" tests/commandline/test_rpr.py

}

main
