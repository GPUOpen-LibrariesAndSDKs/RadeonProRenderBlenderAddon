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

set vs_ver=""
set vs_dir=""

if defined VS140COMNTOOLS (
	set vs_ver=14.0
)

set VsWhere="%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"

if not exist %VsWhere% goto end

set vs_ver=""

for /f "usebackq tokens=1* delims=: " %%i in (`%VsWhere% -latest -requires Microsoft.VisualStudio.Component.VC.140`) do (

if /i "%%i"=="installationVersion" set vs_ver=%%j

if /i "%%i"=="installationPath" set vs_dir=%%j
)

:end
::echo %vs_ver%
::echo %vs_dir%
