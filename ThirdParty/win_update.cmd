@echo off

set ThirdPartyDir="..\..\RadeonProRenderThirdPartyComponents"

if exist %ThirdPartyDir% ( 
	if "%1"=="check_thirdparty" (
		echo Checking %ThirdPartyDir% 
	    echo ===============================================================
	    pushd %ThirdPartyDir% 
    	git remote update
	    git status -uno
		popd
	)
	
    rd /S /Q "RadeonProRender SDK"
    rd /S /Q RadeonProImageProcessing
    rd /S /Q RadeonProRender-GLTF
    rd /S /Q glew

    xcopy /S /Y /I "%ThirdPartyDir%\RadeonProRender SDK\*" "RadeonProRender SDK"
    xcopy /S /Y /I %ThirdPartyDir%\RadeonProImageProcessing\* RadeonProImageProcessing
    xcopy /S /Y /I %ThirdPartyDir%\RadeonProRender-GLTF\* RadeonProRender-GLTF
    xcopy /S /Y /I %ThirdPartyDir%\glew\* glew

) else ( 
    echo Cannot update as %ThirdPartyDir% missing
)
