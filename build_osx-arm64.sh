#!/bin/bash

arch -arm64 python3.9 cmd_tools/create_sdk.py

IGNORE_MISSING_OPENMP=1
cxml="/usr/local/bin/castxml"
if [ -f "$cxml" ]; then
	arch -arm64 python3.9 src/bindings/pyrpr/src/pyrprapi.py $cxml
	if [ -f "./bindings-ok" ]; then
  	arch -arm64 python3.9 build.py
	else
		echo Compiling bindings failed
	fi
else
	echo Error : $cxml is required for build
fi


