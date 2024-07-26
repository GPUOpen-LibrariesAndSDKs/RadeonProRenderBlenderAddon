@echo off


REM set Debug Mode flag

set RPR_BLENDER_DEBUG=0

python3.11 cmd_render.py final_render.py

@REM pause
