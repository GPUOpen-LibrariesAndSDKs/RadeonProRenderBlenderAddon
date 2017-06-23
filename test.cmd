echo off
if ""=="%BLENDER_EXE%" goto error 

py -3.5 test.py
exit

:error
echo "Please set BLENDER_EXE environment variable"