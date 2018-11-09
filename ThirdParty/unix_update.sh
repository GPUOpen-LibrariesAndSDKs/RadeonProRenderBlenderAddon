#!/bin/bash

ThirdPartyDir="../../RadeonProRenderThirdPartyComponents"

if [ -d "$ThirdPartyDir" ]; then
    echo Updating $ThirdPartyDir

    rm -rf 'RadeonProImageProcessing'
    rm -rf 'RadeonProRender SDK'
    rm -rf RadeonProRender-GLTF

    cp -r $ThirdPartyDir/RadeonProImageProcessing RadeonProImageProcessing
    cp -r "$ThirdPartyDir/RadeonProRender SDK" "RadeonProRender SDK"
    cp -r $ThirdPartyDir/RadeonProRender-GLTF RadeonProRender-GLTF
	
    echo ===============================================================
    pushd $ThirdPartyDir 
    git remote update
    git status -uno
    popd
	
else
    echo Cannot update as $ThirdPartyDir missing
fi
