@echo off

setlocal enabledelayedexpansion

:check_castxml

set castxml=%1

if "%castxml%"=="" (
	echo Please set a path to castxml tool as the first parameter.
	goto end
) else (
	echo Path to castxml tool %castxml%

	goto vs_setup
)

:vs_setup

call vs_path.bat

:: VS not detected
if %vs_ver%=="" goto vs_error

:: check VS version
set vs_major=%vs_ver:~0,2%

if %vs_major%==14 (
	echo Visual Studio 2015 is installed.
	
	goto build_plugin
)

set vs17=""

if %vs_major%==15 (
	echo Visual Studio 2017 is installed.
	echo "%vs_dir%"

	echo Trying to setup toolset 14 [Visual Studio 2015] of Visual Studio 2017.

	set vs17="%vs_dir%\VC\Auxiliary\Build\vcvarsall.bat"

	pushd .	
	call !vs17! amd64 -vcvars_ver=14.0
	popd

	goto build_plugin
)

:vs_error
	echo Visual Studio 2015 or newer has to be installed.
	echo Newer version of Visual Studio will be used if it's present (v140 toolset has to be installed).
	goto end

:build_plugin

py -3.5 src\bindings\pyrpr\src\pyrprapi.py %castxml%
	
py -3.5 build.py

:end
