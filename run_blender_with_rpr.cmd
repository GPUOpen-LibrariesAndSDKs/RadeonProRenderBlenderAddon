if ""=="%BLENDER_EXE%" goto error 

#set PYTHONPATH=C:\Program Files\Python35\lib\site-packages

py tests/commandline/run_blender.py "%BLENDER_EXE%" tests/commandline/test_rpr.py
exit

:error
echo "Please set BLENDER_EXE environment variable"
