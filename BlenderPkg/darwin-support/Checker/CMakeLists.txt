cmake_minimum_required(VERSION 3.1)

find_package(OpenCL REQUIRED)
include_directories(${OpenCL_INCLUDE_DIRS})
#link_directories(${OpenCL_LIBRARY})

set(SOURCE_FILES
  checker.cpp
  formSelect.cpp
  formSelect.h)

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../.sdk/rpr/inc"
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../.sdk/rpr/rprTools"
    )

add_executable(checker  ${SOURCE_FILES})
set_target_properties(checker PROPERTIES COMPILE_FLAGS "-std=c++11")

if (${APPLE})
    target_link_libraries(checker ${OpenCL_LIBRARIES})
else()
    target_link_libraries(checker dl pci ${OpenCL_LIBRARIES})
endif()
