cmake_minimum_required(VERSION 3.0)

project(test_trace)

set(RPR_SDK_PATH "${CMAKE_SOURCE_DIR}/../../../../ThirdParty/RadeonProRender SDK/Win")

if (NOT EXISTS "${RPR_SDK_PATH}")
    message(FATAL_ERROR "not exists RPR_SDK_PATH=${RPR_SDK_PATH}")
endif() 

set(src_pattern "${TRACE_PATH}/*.cpp")

file(GLOB result "${src_pattern}")

if (NOT result)
    message(FATAL_ERROR "couldn't find source files in TRACE_PATH=${src_pattern}")
endif()

add_executable(app ${result})

target_link_libraries(app "${RPR_SDK_PATH}/lib/RadeonProRender64.lib")
target_include_directories(app PRIVATE "${RPR_SDK_PATH}/inc")
