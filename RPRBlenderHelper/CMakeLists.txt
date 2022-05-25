cmake_minimum_required(VERSION 3.0)

project(RPRBlenderHelper)

set(CMAKE_VERBOSE_MAKEFILE ON)
set (CMAKE_CXX_STANDARD 11)

set(RPR_SDK_DIR ${CMAKE_SOURCE_DIR}/../.sdk/rpr)
set(RPRTOOLS_DIR ${RPR_SDK_DIR}/rprTools)
set(SHARED_DIR ${CMAKE_SOURCE_DIR}/../RadeonProRenderSharedComponents)

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
        RPRBlenderHelper/dllmain.cpp
    )
    include_directories(
        ${SHARED_DIR}/RadeonProRenderLibs/rprLibs
	)
    set(LIBS
        ${RPR_SDK_DIR}/lib/RadeonProRender64.lib
    )

elseif(${APPLE})
    include_directories(
        ${SHARED_DIR}/RadeonProRenderLibs/rprLibs
    )
    set(LIBS
        ${RPR_SDK_DIR}/bin/libRadeonProRender64.dylib
    )

else()  # Linux
    set(LIBS ${RPR_SDK_DIR}/bin/libRadeonProRender64.so)

endif()

add_library(RPRBlenderHelper SHARED ${SOURCES})
add_definitions(-DBLENDER_PLUGIN)
target_link_libraries(RPRBlenderHelper ${LIBS})


# Building RPRBlenderHelper with OPENVDB support

if("${UNIX}" OR "${APPLE}")
    # for Linux and Mac openvdb isn't supported yet
    return()
endif()

set(OPENVDB_SDK_PATH ${SHARED_DIR}/OpenVdb)

list(APPEND SOURCES
    RPRBlenderHelper/OpenVdb.cpp
)
include_directories(
    ${OPENVDB_SDK_PATH}/include
)

if(WIN32)
    list(APPEND LIBS
        ${OPENVDB_SDK_PATH}/Windows/lib/openvdb.lib
        ${OPENVDB_SDK_PATH}/Windows/lib/tbb.lib
    )
endif()

add_library(RPRBlenderHelper_vdb SHARED ${SOURCES})
add_definitions(-DBLENDER_PLUGIN)
target_link_libraries(RPRBlenderHelper_vdb ${LIBS})
