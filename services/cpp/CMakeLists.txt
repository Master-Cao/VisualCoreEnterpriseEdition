cmake_minimum_required(VERSION 3.16)
project(VisualCoreEnterpriseEdition_CPP LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 设置通用输出目录
set(VC_OUT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/dist")
file(MAKE_DIRECTORY ${VC_OUT_DIR})

message(STATUS "")
message(STATUS "========================================")
message(STATUS "Visual Core Enterprise Edition C++ Modules")
message(STATUS "========================================")
message(STATUS "")

# 选项：可以选择性编译模块
option(BUILD_CAMERA_MODULE "Build camera module" ON)
option(BUILD_DETECTION_MODULE "Build detection module" ON)

# 编译相机模块
if(BUILD_CAMERA_MODULE)
    message(STATUS "Configuring Camera Module...")
    add_subdirectory(camera)
    message(STATUS "Camera Module configured.")
    message(STATUS "")
endif()

# 编译检测模块
if(BUILD_DETECTION_MODULE)
    message(STATUS "Configuring Detection Module...")
    add_subdirectory(detection)
    message(STATUS "Detection Module configured.")
    message(STATUS "")
endif()

message(STATUS "========================================")
message(STATUS "All modules configured successfully!")
message(STATUS "Output directory: ${VC_OUT_DIR}")
message(STATUS "========================================")
message(STATUS "")

# 构建说明
message(STATUS "Build Instructions:")
message(STATUS "  mkdir build && cd build")
message(STATUS "  cmake ..")
message(STATUS "  cmake --build .")
message(STATUS "")
message(STATUS "To disable a module:")
message(STATUS "  cmake -DBUILD_CAMERA_MODULE=OFF ..")
message(STATUS "  cmake -DBUILD_DETECTION_MODULE=OFF ..")
message(STATUS "")
