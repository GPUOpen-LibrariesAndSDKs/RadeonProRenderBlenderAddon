cmake_minimum_required(VERSION 3.0)

project(app)

add_executable(app main.cpp)
target_link_libraries(app OpenGL32)

add_library(lib SHARED lib.cpp)
target_link_libraries(lib OpenGL32)


add_dependencies(app lib)