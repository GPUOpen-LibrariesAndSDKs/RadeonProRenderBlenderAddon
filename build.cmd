set arg=%1
if "%arg%"=="" goto error

python src\bindings\pyrpr\src\pyrprapi.py %arg%
py -3.5 build.py

:error
echo "Please pass castxml path"