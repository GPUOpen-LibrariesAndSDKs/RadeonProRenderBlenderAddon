
echo off
set ThirdPartyDir="..\..\RadeonProRenderThirdPartyComponents"

IF exist %ThirdPartyDir% ( 
    echo Updating %ThirdPartyDir% 

    rd /S /Q AxfPackage
    rd /S /Q 'Expat 2.1.0'
    rd /S /Q OpenCL
    rd /S /Q OpenColorIO
    rd /S /Q 'RadeonProImageProcessing'
    rd /S /Q 'RadeonProRender SDK'
    rd /S /Q RadeonProRender-GLTF
    rd /S /Q ffmpeg
    rd /S /Q glew
    rd /S /Q json
    rd /S /Q oiio
    rd /S /Q oiio-mac
    rd /S /Q synColor

    xcopy /S /Y /I %ThirdPartyDir%\AxfPackage\* AxfPackage
    xcopy /S /Y /I "%ThirdPartyDir%\Expat 2.1.0\*" "Expat 2.1.0"
    xcopy /S /Y /I %ThirdPartyDir%\OpenCL\* "OpenCL"
    xcopy /S /Y /I %ThirdPartyDir%\OpenColorIO\* OpenColorIO
    xcopy /S /Y /I %ThirdPartyDir%\RadeonProImageProcessing\* RadeonProImageProcessing
    xcopy /S /Y /I "%ThirdPartyDir%\RadeonProRender SDK\*" "RadeonProRender SDK"
    xcopy /S /Y /I %ThirdPartyDir%\RadeonProRender-GLTF\* "RadeonProRender-GLTF"
    xcopy /S /Y /I %ThirdPartyDir%\ffmpeg\* ffmpeg
    xcopy /S /Y /I %ThirdPartyDir%\glew\* glew
    xcopy /S /Y /I %ThirdPartyDir%\json\* json
    xcopy /S /Y /I %ThirdPartyDir%\oiio\* oiio
    xcopy /S /Y /I %ThirdPartyDir%\oiio-mac\* oiio-mac
    xcopy /S /Y /I %ThirdPartyDir%\synColor\* synColor

    echo ===============================================================
    pushd %ThirdPartyDir% 
    git remote update
    git status -uno
    popd
	
) ELSE ( 
    echo Cannot update as %ThirdPartyDir% missing
)