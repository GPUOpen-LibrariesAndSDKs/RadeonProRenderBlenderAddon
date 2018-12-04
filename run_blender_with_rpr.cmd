if ""=="%BLENDER_EXE%" goto error 

py cmd_tools/run_blender.py "%BLENDER_EXE%" cmd_tools/test_rpr.py
exit

:error
echo "Please set BLENDER_EXE environment variable"
