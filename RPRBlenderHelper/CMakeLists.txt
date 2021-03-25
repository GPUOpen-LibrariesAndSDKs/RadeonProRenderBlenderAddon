cmake_minimum_required(VERSION 3.0)

project(RPRBlenderHelper)

set(CMAKE_VERBOSE_MAKEFILE ON)
set (CMAKE_CXX_STANDARD 11)

set(RPR_SDK_DIR ${CMAKE_SOURCE_DIR}/../.sdk/rpr)
set(RPRTOOLS_DIR ${RPR_SDK_DIR}/rprTools)
set(SHARED_DIR ${CMAKE_SOURCE_DIR}/../RadeonProRenderSharedComponents)
set(OPENVDB_SDK_PATH ${SHARED_DIR}/OpenVdb)

set(SOURCES
    RPRBlenderHelper/RPRBlenderHelper.cpp
    RPRBlenderHelper/SkyBuilder.cpp
    RPRBlenderHelper/SkyGen.cpp
    ${SHARED_DIR}/src/SunPosition/SPA.cpp
    RPRBlenderHelper/CitiesDatabase.cpp
    ${RPRTOOLS_DIR}/RprTools.cpp
)
include_directories(
    ${RPR_SDK_DIR}/inc
    ${RPRTOOLS_DIR}
    ${SHARED_DIR}/src/SunPosition
)

if(WIN32)
    list(APPEND SOURCES
        RPRBlenderHelper/OpenVdb.cpp
        RPRBlenderHelper/dllmain.cpp
    )
    include_directories(
        ${OPENVDB_SDK_PATH}/include
        ${SHARED_DIR}/RadeonProRenderLibs/rprLibs
	)

    set(LIBS
        ${RPR_SDK_DIR}/lib/RadeonProRender64.lib
        ${OPENVDB_SDK_PATH}/Windows/lib/openvdb.lib
        ${OPENVDB_SDK_PATH}/Windows/lib/Half-2_3.lib
        ${OPENVDB_SDK_PATH}/Windows/lib/tbb.lib
    )

elseif(${APPLE})
    list(APPEND SOURCES
        RPRBlenderHelper/OpenVdb.cpp
    )
    include_directories(
        ${OPENVDB_SDK_PATH}/include
        ${SHARED_DIR}/RadeonProRenderLibs/rprLibs
    )

    set(LIBS
        ${RPR_SDK_DIR}/bin/libRadeonProRender64.dylib
        ${OPENVDB_SDK_PATH}/OSX/lib/libopenvdb.a
        ${OPENVDB_SDK_PATH}/OSX/lib/libz.a
        ${OPENVDB_SDK_PATH}/OSX/lib/libblosc.a
        ${OPENVDB_SDK_PATH}/OSX/lib/libsnappy.a
        ${OPENVDB_SDK_PATH}/OSX/lib/libboost_iostreams.a
        ${OPENVDB_SDK_PATH}/OSX/lib/libtbb.a
    )

else()  # Linux
    set(LIBS ${RPR_SDK_DIR}/bin/libRadeonProRender64.so)

endif()

add_library(RPRBlenderHelper SHARED ${SOURCES})

add_definitions(-DBLENDER_PLUGIN)

target_link_libraries(RPRBlenderHelper ${LIBS})
