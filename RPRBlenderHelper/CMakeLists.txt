cmake_minimum_required(VERSION 3.0)

project(RPRBlenderHelper)

set (CMAKE_CXX_STANDARD 11)

find_package(OpenMP)

if (${APPLE})
    set (IGNORE_MISSING_OPENMP 1)
endif()

if (OPENMP_FOUND)
    set (CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${OpenMP_C_FLAGS}")
    set (CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${OpenMP_CXX_FLAGS}")
else()
    if(NOT "${IGNORE_MISSING_OPENMP}")
        message(FATAL_ERROR "OpenMP support not found! Use IGNORE_MISSING_OPENMP=ON to override.")
    endif() 
endif()


set(RPR_SDK_PATH "${CMAKE_SOURCE_DIR}/../ThirdParty/RadeonProRender SDK")

if (${APPLE})
    set (RPRTOOL "${RPR_SDK_PATH}/Mac/RprTools.cpp")
elseif(${WIN32})
    set (RPRTOOL "${RPR_SDK_PATH}/Win/RprTools.cpp")
else()
    set (RPRTOOL "${RPR_SDK_PATH}/Linux-Ubuntu/RprTools.cpp")
endif()

if (NOT EXISTS "${RPR_SDK_PATH}")
    message(FATAL_ERROR "No RPR SDK at RPR_SDK_PATH=${RPR_SDK_PATH}")
endif() 

set(src
    RPRBlenderHelper/RPRBlenderHelper.cpp
    RPRBlenderHelper/SkyBuilder.cpp
    RPRBlenderHelper/SkyGen.cpp
    RPRBlenderHelper/SunPositionCalculator.cpp
    RPRBlenderHelper/CitiesDatabase.cpp
    "${RPRTOOL}")

if(WIN32)
    list(APPEND src RPRBlenderHelper/dllmain.cpp)
    set(RPR64LIB "${RPR_SDK_PATH}/Win/lib/RadeonProRender64.lib")
else()
    if (${APPLE})
	set(RPR64LIB "${RPR_SDK_PATH}/Mac/lib/libRadeonProRender64.dylib")
    else()
	set(RPR64LIB "${RPR_SDK_PATH}/Linux-Ubuntu/lib/libRadeonProRender64.so")
    endif()
endif()

add_library(RPRBlenderHelper SHARED ${src})

add_definitions(-DBLENDER_PLUGIN)

target_link_libraries(RPRBlenderHelper "${RPR64LIB}")
target_include_directories(RPRBlenderHelper PRIVATE 
	"${RPR_SDK_PATH}/Win"
	"${RPR_SDK_PATH}/Win/inc"
    )


