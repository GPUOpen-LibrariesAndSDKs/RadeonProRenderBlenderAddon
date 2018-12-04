if ""=="%BLENDER_28x_EXE%" goto error 

py cmd_tools/run_blender.py "%BLENDER_28x_EXE%" cmd_tools/test_rpr.py
exit

:error
echo "Please set BLENDER_28x_EXE environment variable"
