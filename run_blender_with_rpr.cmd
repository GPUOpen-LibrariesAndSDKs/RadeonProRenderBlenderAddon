@echo off

REM ******************************************************************
REM  Copyright 2020 Advanced Micro Devices, Inc
REM  Licensed under the Apache License, Version 2.0 (the "License");
REM  you may not use this file except in compliance with the License.
REM  You may obtain a copy of the License at
REM
REM     http://www.apache.org/licenses/LICENSE-2.0
REM
REM  Unless required by applicable law or agreed to in writing, software
REM  distributed under the License is distributed on an "AS IS" BASIS,
REM  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
REM  See the License for the specific language governing permissions and
REM  limitations under the License.
REM  *******************************************************************

@echo on

REM Set the Blender executable path
set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 4.1\blender.exe"

if ""=="%BLENDER_EXE%" goto error

REM set Debug Mode flag
set RPR_BLENDER_DEBUG=1

py -3.11 cmd_tools/run_blender.py "%BLENDER_EXE%" cmd_tools/test_rpr.py
pause
REM it's much easier to get issue traceback on crash if pause is present; remove if not needed
exit

:error
echo "Please set BLENDER_EXE environment variable"
