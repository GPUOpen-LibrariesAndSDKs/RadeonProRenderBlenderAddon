#!/bin/bash

ThirdPartyDir="../../RadeonProRenderThirdPartyComponents"

if [ -d "$ThirdPartyDir" ]; then
    echo Updating $ThirdPartyDir

    rm -rf AxfPackage
    rm -rf 'Expat 2.1.0'
    rm -rf OpenCL
    rm -rf OpenColorIO
    rm -rf 'RadeonProImageProcessing'
    rm -rf 'RadeonProRender SDK'
    rm -rf RadeonProRender-GLTF
    rm -rf ffmpeg
    rm -rf glew
    rm -rf json
    rm -rf oiio
    rm -rf oiio-mac
    rm -rf synColor

    cp -r $ThirdPartyDir/AxfPackage/* AxfPackage
    cp -r "$ThirdPartyDir/Expat 2.1.0/*" "Expat 2.1.0"
    cp -r $ThirdPartyDir/OpenCL/* OpenCL
    cp -r $ThirdPartyDir/OpenColorIO/* OpenColorIO
    cp -r $ThirdPartyDir/RadeonProImageProcessing/* RadeonProImageProcessing
    cp -r "$ThirdPartyDir/RadeonProRender SDK/*" "RadeonProRender SDK"
    cp -r $ThirdPartyDir/RadeonProRender-GLTF/* RadeonProRender-GLTF
    cp -r $ThirdPartyDir/ffmpeg/* ffmpeg
    cp -r $ThirdPartyDir/glew/* glew
    cp -r $ThirdPartyDir/json/* json
    cp -r $ThirdPartyDir/oiio/* oiio
    cp -r $ThirdPartyDir/oiio-mac/* oiio-mac
    cp -r $ThirdPartyDir/synColor/* synColor
	
    echo ===============================================================
    pushd $ThirdPartyDir 
    git remote update
    git status -uno
    popd
	
else
    echo Cannot update as $ThirdPartyDir missing
fi
