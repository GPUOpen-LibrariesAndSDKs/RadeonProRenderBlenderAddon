@echo off


REM set Debug Mode flag

set RPR_BLENDER_DEBUG=0

py -3.11 -m pip install python-dotenv opencv-python scikit-image

py -3.11 cmd_render.py final_render.py

@REM pause
