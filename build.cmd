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

setlocal enabledelayedexpansion

:cleanup
rmdir /S /Q RPRBlenderHelper\.build src\bindings\pyrpr\.build src\bindings\pyrpr\src\__pycache__

:check_castxml
set castxml=RadeonProRenderSharedComponents\castxml\win\bin\castxml.exe

if not exist %castxml% (
	echo Castxml tool is not found.
	goto :eof
) else (
	echo Path to castxml tool %castxml%

	goto :vs_setup
)

:vs_setup
call vs_path.bat

:: VS not detected
if %vs_ver%=="" goto :vs_error

:: check VS version
set vs_major=%vs_ver:~0,2%

if %vs_major%==14 (
	echo Visual Studio 2015 is installed.
	
	goto :build_plugin
)

set vs17=""

if %vs_major%==15 or %vs_major%==16 (
	echo Visual Studio 2017/2019 is installed.
	echo "%vs_dir%"

	echo Trying to setup toolset 14 [Visual Studio 2015] of Visual Studio 2017/2019.

	set vs17="%vs_dir%\VC\Auxiliary\Build\vcvarsall.bat"

	pushd .	
	call !vs17! amd64 -vcvars_ver=14.0
	popd

	goto :build_plugin
)

:vs_error
	echo Visual Studio 2015 or newer has to be installed.
	echo Newer version of Visual Studio will be used if it's present (v140 toolset has to be installed).
	goto :eof

:build_plugin
py -3.7 cmd_tools\create_sdk.py
py -3.7 src\bindings\pyrpr\src\pyrprapi.py %castxml%

set bindingsOk=.\bindings-ok
if exist %bindingsOk% (
	py -3.7 build.py
	py -3.9 build.py
) else (
	echo Compiling bindings failed
)
