cmake_minimum_required(VERSION 3.16)
project(vc_camera_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Python和pybind11配置
# 自动查找Python3（如果需要指定特定版本，可以通过-DPython3_ROOT_DIR传递）
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
message(STATUS "找到Python3: ${Python3_EXECUTABLE}")
message(STATUS "Python3版本: ${Python3_VERSION}")
message(STATUS "Python3包含目录: ${Python3_INCLUDE_DIRS}")
message(STATUS "Python3库: ${Python3_LIBRARIES}")

# 查找pybind11
# 方法1: 通过CMake配置文件查找
find_package(pybind11 CONFIG QUIET)

# 方法2: 如果方法1失败，尝试通过python导入pybind11
if(NOT pybind11_FOUND)
    message(STATUS "未找到pybind11 CMake配置，尝试通过Python查找...")
    execute_process(
        COMMAND "${Python3_EXECUTABLE}" -c "import pybind11; print(pybind11.get_cmake_dir())"
        OUTPUT_VARIABLE pybind11_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
    if(pybind11_DIR)
        message(STATUS "从Python获取到pybind11路径: ${pybind11_DIR}")
        find_package(pybind11 CONFIG REQUIRED)
    else()
        message(FATAL_ERROR "未找到pybind11，请安装: pip install pybind11")
    endif()
endif()

message(STATUS "pybind11版本: ${pybind11_VERSION}")

# SICK Visionary源文件
file(GLOB SICK_SRC "${CMAKE_CURRENT_SOURCE_DIR}/../../../infrastructure/sick_visionary_cpp_shared/src/*.cpp")

# 创建相机模块
add_library(vc_camera_cpp_module MODULE 
    bindings.cpp 
    VisionaryCameraLib.cpp 
    ${SICK_SRC}
)

target_include_directories(vc_camera_cpp_module PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../infrastructure/sick_visionary_cpp_shared/src
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../infrastructure/sick_visionary_cpp_shared/3pp
)

target_link_libraries(vc_camera_cpp_module PRIVATE pybind11::module)

set_target_properties(vc_camera_cpp_module PROPERTIES 
    PREFIX "" 
    OUTPUT_NAME "vc_camera_cpp"
)

if (WIN32)
    set_target_properties(vc_camera_cpp_module PROPERTIES SUFFIX ".pyd")
endif()

# 输出目录
set(VC_OUT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../dist")
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

