cxml="/usr/bin/castxml"
if [ -f "$cxml" ]; then
	python3 src/bindings/pyrpr/src/pyrprapi.py $cxml
	python3 build.py
else
	echo Error : $cxml is required for build
fi
