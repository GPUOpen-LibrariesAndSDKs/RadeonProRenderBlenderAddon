
set ThirdPartyDir="../../RadeonProRenderThirdPartyComponents"

IF exist $ThirdPartyDir ( 
    echo Updating $ThirdPartyDir

    rm -rf AxfPackage
    rm -rf 'Expat 2.1.0'
    rm -rf OpenCL
    rm -rf OpenColorIO
    rm -rf 'RadeonProRender SDK'
    rm -rf RadeonProRender-GLTF
    rm -rf ffmpeg
    rm -rf glew
    rm -rf json
    rm -rf oiio
    rm -rf oiio-mac
    rm -rf synColor

    cp -r $ThirdPartyDir/* .

) ELSE ( 
    echo Cannot update as %ThirdPartyDir% missing
)