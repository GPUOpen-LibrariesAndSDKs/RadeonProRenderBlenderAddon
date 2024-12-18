#!/bin/bash

python3.11 cmd_tools/create_sdk.py

IGNORE_MISSING_OPENMP=1
cxml="/usr/local/bin/castxml"
if [ -f "$cxml" ]; then
	python3.11 src/bindings/pyrpr/src/pyrprapi.py $cxml
	if [ -f "./bindings-ok" ]; then
		python3.11 build.py
	else
		echo Compiling bindings failed
	fi
else
	echo Error : $cxml is required for build
fi


