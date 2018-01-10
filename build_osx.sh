IGNORE_MISSING_OPENMP=1
cxml="/usr/local/bin/castxml"
if [ -f "$cxml" ]; then
	python3 src/bindings/pyrpr/src/pyrprapi.py $cxml
	python3 build.py
	sh osx/postbuild.sh
else
	echo Error : $cxml is required for build
fi


