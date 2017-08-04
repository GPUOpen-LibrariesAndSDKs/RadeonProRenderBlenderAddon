if ""=="%BLENDER_EXE%" goto error 

py tests/commandline/run_blender.py "%BLENDER_EXE%" tests/commandline/test_rpr.py
exit

:error
echo "Please set BLENDER_EXE environment variable"
