@echo off

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
rmdir /S /Q __pycache__ out output system ThirdParty Installer\PluginInstaller\bin Installer\PluginInstaller\Generated Installer\PluginInstaller\obj

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

:: update ThirdParty
xcopy /S /Y /I ..\ThirdParty\OpenCL\* ThirdParty\OpenCL

:: copy files
call py -3.7 build_win_installer.py

:: build
call build.cmd

move "Installer\PluginInstaller\bin\x64\Release\PluginInstaller.msi" "RadeonProRenderBlender_%BLENDER_PLUGIN_VERSION%.msi"
