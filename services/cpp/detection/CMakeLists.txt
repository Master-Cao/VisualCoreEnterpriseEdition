cmake_minimum_required(VERSION 3.16)
project(vc_detection_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
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

# YOLOv8-Seg项目路径
# 使用绝对路径来避免相对路径解析问题
get_filename_component(PROJECT_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../.." ABSOLUTE)
set(YOLOV8_SEG_PATH "${PROJECT_ROOT}/infrastructure/yolov8-seg-thread-stream")

message(STATUS "项目根目录: ${PROJECT_ROOT}")
message(STATUS "YOLOv8-Seg路径: ${YOLOV8_SEG_PATH}")

# 检查YOLOv8-Seg项目是否存在
if(NOT EXISTS "${YOLOV8_SEG_PATH}")
    message(FATAL_ERROR "YOLOv8-Seg项目未找到: ${YOLOV8_SEG_PATH}\n请确保已将yolov8-seg-thread-stream放置在infrastructure目录下")
endif()

if(NOT EXISTS "${YOLOV8_SEG_PATH}/CMakeLists.txt")
    message(FATAL_ERROR "YOLOv8-Seg项目不完整: 缺少CMakeLists.txt")
endif()

# 检测系统架构
if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64")
    set(LIB_ARCH "aarch64")
elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "arm")
    set(LIB_ARCH "armhf")
else()
    set(LIB_ARCH "aarch64")  # 默认
    message(WARNING "未识别的架构: ${CMAKE_SYSTEM_PROCESSOR}, 默认使用 aarch64")
endif()

# 检测设备类型（可通过 -DDEVICE_NAME=RK3588 传递）
if(NOT DEFINED DEVICE_NAME)
    set(DEVICE_NAME "RK3588")
endif()

message(STATUS "目标架构: ${LIB_ARCH}")
message(STATUS "目标设备: ${DEVICE_NAME}")

# RKNN API路径
set(RKNN_API_PATH "${YOLOV8_SEG_PATH}/librknn_api")
set(RKNN_INCLUDE_DIR "${RKNN_API_PATH}/include")

# 根据平台选择RKNN库文件
if(WIN32)
    # Windows平台 - RKNN不支持，提供Mock或跳过
    message(WARNING "")
    message(WARNING "=======================================================")
    message(WARNING "RKNN库不支持Windows平台")
    message(WARNING "检测模块将仅编译接口，不包含实际RKNN功能")
    message(WARNING "如需使用检测功能，请在Linux/ARM平台上编译")
    message(WARNING "=======================================================")
    message(WARNING "")
    set(RKNN_AVAILABLE FALSE)
    set(RKNN_LIB_PATH "")
else()
    # Linux/ARM平台
    set(RKNN_LIB_PATH "${RKNN_API_PATH}/${LIB_ARCH}/librknnrt.so")
    
    # RGA库路径
    set(RGA_DIR "${YOLOV8_SEG_PATH}/3rdparty/rga/${DEVICE_NAME}")
    set(RGA_INCLUDE_DIR "${RGA_DIR}/include")
    set(RGA_LIB_PATH "${RGA_DIR}/lib/Linux/${LIB_ARCH}/librga.so")
    
    # 检查RKNN库是否存在
    if(NOT EXISTS "${RKNN_INCLUDE_DIR}/rknn_api.h")
        message(FATAL_ERROR "RKNN API头文件未找到: ${RKNN_INCLUDE_DIR}/rknn_api.h")
    endif()
    
    if(NOT EXISTS "${RKNN_LIB_PATH}")
        message(FATAL_ERROR "RKNN库未找到: ${RKNN_LIB_PATH}")
    endif()
    
    set(RKNN_AVAILABLE TRUE)
    message(STATUS "RKNN库路径: ${RKNN_LIB_PATH}")
endif()

# 查找OpenCV（可选，用于高级图像处理）
find_package(OpenCV QUIET)
if(OpenCV_FOUND)
    message(STATUS "找到OpenCV版本: ${OpenCV_VERSION}")
    message(STATUS "OpenCV包含目录: ${OpenCV_INCLUDE_DIRS}")
    set(USE_OPENCV TRUE)
else()
    message(STATUS "未找到OpenCV，将使用基础图像处理功能")
    set(USE_OPENCV FALSE)
endif()

# 创建检测模块
add_library(vc_detection_cpp_module MODULE 
    bindings.cpp 
    RKNNDetector.cpp
)

target_include_directories(vc_detection_cpp_module PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${RKNN_INCLUDE_DIR}
    ${YOLOV8_SEG_PATH}/src
)

# 如果使用OpenCV，添加OpenCV头文件
if(USE_OPENCV)
    target_include_directories(vc_detection_cpp_module PRIVATE ${OpenCV_INCLUDE_DIRS})
    target_compile_definitions(vc_detection_cpp_module PRIVATE USE_OPENCV)
endif()

# 如果RKNN可用，添加RKNN支持
if(RKNN_AVAILABLE)
    target_compile_definitions(vc_detection_cpp_module PRIVATE RKNN_AVAILABLE)
    
    # 如果RGA库存在，添加RGA支持
    if(EXISTS "${RGA_INCLUDE_DIR}" AND EXISTS "${RGA_LIB_PATH}")
        message(STATUS "找到RGA库: ${RGA_LIB_PATH}")
        target_include_directories(vc_detection_cpp_module PRIVATE ${RGA_INCLUDE_DIR})
        target_compile_definitions(vc_detection_cpp_module PRIVATE USE_RGA)
        set(USE_RGA TRUE)
    else()
        message(STATUS "RGA库不可用，将不使用硬件加速")
        set(USE_RGA FALSE)
    endif()
else()
    message(STATUS "RKNN不可用，将编译空接口版本")
    set(USE_RGA FALSE)
endif()

# 链接库
target_link_libraries(vc_detection_cpp_module PRIVATE 
    pybind11::module
)

# 如果RKNN可用，链接RKNN库
if(RKNN_AVAILABLE AND RKNN_LIB_PATH)
    target_link_libraries(vc_detection_cpp_module PRIVATE ${RKNN_LIB_PATH})
endif()

# 如果使用OpenCV，链接OpenCV库
if(USE_OPENCV)
    target_link_libraries(vc_detection_cpp_module PRIVATE ${OpenCV_LIBS})
endif()

# 如果使用RGA，链接RGA库
if(USE_RGA)
    target_link_libraries(vc_detection_cpp_module PRIVATE ${RGA_LIB_PATH})
endif()

set_target_properties(vc_detection_cpp_module PROPERTIES 
    PREFIX "" 
    OUTPUT_NAME "vc_detection_cpp"
)

if(WIN32)
    set_target_properties(vc_detection_cpp_module PROPERTIES SUFFIX ".pyd")
endif()

# 输出目录
set(VC_OUT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../dist")
file(MAKE_DIRECTORY ${VC_OUT_DIR})

set_target_properties(vc_detection_cpp_module PROPERTIES 
    RUNTIME_OUTPUT_DIRECTORY ${VC_OUT_DIR}
    LIBRARY_OUTPUT_DIRECTORY ${VC_OUT_DIR}
    ARCHIVE_OUTPUT_DIRECTORY ${VC_OUT_DIR}
)

install(TARGETS vc_detection_cpp_module 
    RUNTIME DESTINATION ${VC_OUT_DIR}
    LIBRARY DESTINATION ${VC_OUT_DIR}
    ARCHIVE DESTINATION ${VC_OUT_DIR}
)

# 打印配置信息
message(STATUS "")
message(STATUS "==== Detection Module Configuration ====")
message(STATUS "YOLOv8-Seg Path: ${YOLOV8_SEG_PATH}")
message(STATUS "RKNN Include: ${RKNN_INCLUDE_DIR}")
message(STATUS "RKNN Library: ${RKNN_LIB_PATH}")
message(STATUS "Architecture: ${LIB_ARCH}")
message(STATUS "Device: ${DEVICE_NAME}")
message(STATUS "OpenCV: ${USE_OPENCV}")
message(STATUS "RGA: ${USE_RGA}")
message(STATUS "Output Dir: ${VC_OUT_DIR}")
message(STATUS "=========================================")
message(STATUS "")

