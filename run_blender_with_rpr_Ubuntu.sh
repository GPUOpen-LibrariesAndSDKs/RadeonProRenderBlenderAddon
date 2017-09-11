#!/bin/bash

CDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RPR_SDK="$CDIR/radeonprorendersdk"

BLENDER_EXE="/usr/bin/blender"

export LD_LIBRARY_PATH="$RPR_SDK"

python3 tests/commandline/run_blender.py "$BLENDER_EXE" tests/commandline/test_rpr.py
exit

