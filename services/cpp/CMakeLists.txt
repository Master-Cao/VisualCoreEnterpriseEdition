cmake_minimum_required(VERSION 3.16)
project(vc_camera_cpp LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(Python3_ROOT_DIR "C:/ProgramData/miniconda3/envs/sick")
set(Python3_EXECUTABLE "C:/ProgramData/miniconda3/envs/sick/python.exe")
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
set(PYTHON_EXECUTABLE "${Python3_EXECUTABLE}")
set(pybind11_DIR "C:/ProgramData/miniconda3/envs/sick/lib/site-packages/pybind11/share/cmake/pybind11")
find_package(pybind11 REQUIRED CONFIG)
file(GLOB SICK_SRC "${CMAKE_CURRENT_SOURCE_DIR}/../../infrastructure/sick_visionary_cpp_shared/src/*.cpp")
add_library(vc_camera_cpp_module MODULE bindings.cpp VisionaryCameraLib.cpp ${SICK_SRC})
target_include_directories(vc_camera_cpp_module PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/../../infrastructure/sick_visionary_cpp_shared/src
    ${CMAKE_CURRENT_SOURCE_DIR}/../../infrastructure/sick_visionary_cpp_shared/3pp
)
target_link_libraries(vc_camera_cpp_module PRIVATE pybind11::module)
set_target_properties(vc_camera_cpp_module PROPERTIES PREFIX "" OUTPUT_NAME "vc_camera_cpp")
if (WIN32)
  set_target_properties(vc_camera_cpp_module PROPERTIES SUFFIX ".pyd")
endif()

# Explicit output directory to make artifact easier to find
set(VC_OUT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/dist")
file(MAKE_DIRECTORY ${VC_OUT_DIR})
set_target_properties(vc_camera_cpp_module PROPERTIES 
  RUNTIME_OUTPUT_DIRECTORY ${VC_OUT_DIR}
  LIBRARY_OUTPUT_DIRECTORY ${VC_OUT_DIR}
  ARCHIVE_OUTPUT_DIRECTORY ${VC_OUT_DIR}
)

install(TARGETS vc_camera_cpp_module 
  RUNTIME DESTINATION ${VC_OUT_DIR}
  LIBRARY DESTINATION ${VC_OUT_DIR}
  ARCHIVE DESTINATION ${VC_OUT_DIR}
)
