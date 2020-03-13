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

:get_plugin_version
powershell -executionPolicy bypass -file GetVersion.ps1

if %ERRORLEVEL% neq 0 (
  echo Can not detect version of the plugin [error %ERRORLEVEL%].
  exit /B %ERRORLEVEL%
)

for /f %%v in ('powershell -executionPolicy bypass -file GetVersion.ps1') do (
	set BLENDER_PLUGIN_VERSION=%%v
)

echo Building Radeon ProRender AddOn for Blender %BLENDER_PLUGIN_VERSION%

:cleanup
del /F RadeonProRenderBlender_*.msi
del /F addon.zip
rmdir /S /Q __pycache__ out output system Installer\PluginInstaller\bin Installer\PluginInstaller\Generated Installer\PluginInstaller\obj

:: parse options
if "%1"=="clean" goto :eof

if "%1"=="build_installer" goto :build_installer

:: verify Python
:: using py python runner on windows to use the python user has configured
call py -3.7 --version

if %ERRORLEVEL% equ 9009 (
	echo python not found
	exit /B 1
)

:build_plugin

pushd ..\
call build.cmd
popd

:build_installer

:: copy files
call py -3.7 build_win_installer.py

:: build
call build.cmd

move "Installer\PluginInstaller\bin\x64\Release\PluginInstaller.msi" "RadeonProRenderBlender_%BLENDER_PLUGIN_VERSION%.msi"
