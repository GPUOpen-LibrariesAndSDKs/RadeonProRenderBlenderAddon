echo off
set castxml=%1
if "%castxml%"=="" (
	echo Please pass the path to castxml tool as the first parameter.
) else (
	echo CastXml found at %castxml%
	py -3.5 src\bindings\pyrpr\src\pyrprapi.py %castxml%
	py -3.5 build.py
)
