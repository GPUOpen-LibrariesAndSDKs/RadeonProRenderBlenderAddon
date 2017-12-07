
echo off
set ThirdPartyDir="..\..\RadeonProRenderThirdPartyComponents"

IF exist %ThirdPartyDir% ( 
    echo Updating %ThirdPartyDir% 

    rd /S /Q AxfPackage
    rd /S /Q 'Expat 2.1.0'
    rd /S /Q OpenCL
    rd /S /Q OpenColorIO
    rd /S /Q 'RadeonProRender SDK'
    rd /S /Q RadeonProRender-GLTF
    rd /S /Q ffmpeg
    rd /S /Q glew
    rd /S /Q json
    rd /S /Q oiio
    rd /S /Q oiio-mac
    rd /S /Q synColor

    xcopy /S /Y /I %ThirdPartyDir%\* .

) ELSE ( 
    echo Cannot update as %ThirdPartyDir% missing
)