#!/bin/bash

PYTHON_VERSION=`python3 --version`

if [[ $PYTHON_VERSION =~ 'Python 3.5.' ]]; then
    echo Found correct python version
else
    echo Incorrect version of python in path: $PYTHON_VERSION
    exit 1
fi


IGNORE_MISSING_OPENMP=1
cxml="/usr/local/bin/castxml"
if [ -f "$cxml" ]; then
	python3 src/bindings/pyrpr/src/pyrprapi.py $cxml
	if [ -f "./bindings-ok" ]; then
		python3 build.py
		sh osx/postbuild.sh
	else
		echo Compiling bindings failed
	fi
else
	echo Error : $cxml is required for build
fi


