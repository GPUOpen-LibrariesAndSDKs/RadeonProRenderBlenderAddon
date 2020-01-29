@echo off

setlocal enabledelayedexpansion

:vs_setup

call vs_path.bat

:: VS not detected
if %vs_ver%=="" goto :vs_error

:: check VS version
set vs_major=%vs_ver:~0,2%

if %vs_major%==14 (
	echo Visual Studio 2015 is installed.
	
	pushd "%VS140COMNTOOLS%..\..\VC"
	call vcvarsall.bat amd64
	popd

	goto :build_installer
)

set vs17=""

if %vs_major% GEQ 15 (
	echo Visual Studio 2017/2019 is installed.
	echo "%vs_dir%"

	echo Trying to setup toolset 14 [Visual Studio 2015] of Visual Studio 2017/2019.

	set vs17="%vs_dir%\VC\Auxiliary\Build\vcvarsall.bat"

	pushd .	
	call !vs17! amd64 -vcvars_ver=14.0
	popd

	goto :build_installer
)

:vs_error
	echo Visual Studio 2015 or newer has to be installed.
	echo Newer version of Visual Studio will be used if it's present (v140 toolset has to be installed).
	goto :eof

:build_installer

msbuild Installer/PluginInstaller.sln /property:Configuration=Release /property:Platform=x64
