#!/bin/bash

#**********************************************************************
# Copyright 2024 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

RPR_SDK="$DIR/RadeonProRenderSDK"
RIF_SDK="$DIR/RadeonProImageProcessingSDK"

WORK_DIR=$1
USE_TMP=false

if [ -z $WORK_DIR ]; then
	WORK_DIR=`mktemp -d -p /tmp rpr_blender_workdir_XXXXXXXX`
	echo "WORK_DIR not set. Use tmp workdir $WORK_DIR"
	USE_TMP=true
fi

function prepare_runtime()
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
	find "$RPR_SDK/RadeonProRender/binUbuntu20" -name "*.so" -type f -exec ln -sf {} "$WORK_DIR" \;

	# link hip kernels
	ln -sf $RPR_SDK/hipbin $WORK_DIR/hipbin

	# link imageprocessing lib to workdir
	find "$RIF_SDK/Ubuntu20/Dynamic" -name "*.so" -type f -exec ln -sf {} "$WORK_DIR" \;

	# link helper to workdir
	ln -sf "$DIR/RPRBlenderHelper/.build/libRPRBlenderHelper.so" "$WORK_DIR/"
}

# deletes the work directory
function cleanup {      
	if $USE_TMP; then
		echo "drop tmpdir $WORK_DIR"
		rm -rf "$WORK_DIR"
	fi
}

# register the cleanup function to be called on the EXIT signal
trap cleanup EXIT

function main() 
{
	prepare_runtime

  	export RPR_BLENDER_DEBUG=1
	export LD_LIBRARY_PATH="$WORK_DIR:$LD_LIBRARY_PATH"

	python3.11 cmd_tools/run_blender.py "$BLENDER_EXE" cmd_tools/test_rpr.py

}

main
