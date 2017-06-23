cmake_minimum_required(VERSION 3.0)

if (UNIX)
    include(CheckCXXCompilerFlag)
    if (CMAKE_VERSION VERSION_LESS "3.1")
       if (CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
          set (CMAKE_CXX_FLAGS "--std=gnu++11 ${CMAKE_CXX_FLAGS}")
    endif ()
    else ()
      set (CMAKE_CXX_STANDARD 11)
    endif ()
endif (UNIX)

project(core_test)

set(RPR_SDK_PATH "${CMAKE_SOURCE_DIR}/../../ThirdParty/RadeonProRender SDK")

if (NOT EXISTS "${RPR_SDK_PATH}")
    message(FATAL_ERROR "not exists RPR_SDK_PATH=${RPR_SDK_PATH}")
endif() 

add_executable(test_context test_context.cpp)
if (NOT UNIX)
   add_executable(test_multithreading test_multithreading.cpp)
   add_executable(test_many_contexts test_many_contexts.cpp)
   add_executable(test_cpu_context_restart test_cpu_context_restart.cpp)
endif ()

if (UNIX)
   link_directories(../../Bin/${BUILD_PATH}) 

   foreach(name test_context)
        target_link_libraries("${name}" "${RPR_SDK_PATH}/Linux/lib/libRadeonProRender64.so")
        target_include_directories("${name}" PRIVATE "${RPR_SDK_PATH}/Linux/inc")
   endforeach()
else ()
   foreach(name test_context test_multithreading test_many_contexts test_cpu_context_restart)
       target_link_libraries("${name}" "${RPR_SDK_PATH}/Win/lib/RadeonProRender64.lib")
       target_include_directories("${name}" PRIVATE "${RPR_SDK_PATH}/Win/inc")
   endforeach()
endif()

