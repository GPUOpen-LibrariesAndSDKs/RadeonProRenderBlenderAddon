@echo off

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
