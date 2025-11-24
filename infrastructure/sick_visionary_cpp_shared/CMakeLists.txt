#
# Copyright note: Redistribution and use in source, with or without modification, are permitted.
# 
# Updated: January 2020
# 
# SICK AG, Waldkirch
# email: TechSupport0905@sick.de

cmake_minimum_required(VERSION 3.16)

project(sick_visionary_cpp_shared
        VERSION 1.2.0
        LANGUAGES CXX)

### COMPILER FLAGS ###
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(Boost)

### BUILD ###
file(GLOB HEADERS src/*.h)
aux_source_directory(src SRC_LIST)

add_library(${PROJECT_NAME} STATIC ${SRC_LIST} ${HEADERS})

set_target_properties(${PROJECT_NAME} PROPERTIES
  CXX_STANDARD 11
  CXX_STANDARD_REQUIRED YES
  CXX_EXTENSIONS OFF)

target_include_directories(${PROJECT_NAME} PUBLIC include src)

if(NOT Boost_FOUND)
target_include_directories(${PROJECT_NAME} PUBLIC 3pp)
endif()

if(WIN32)
  target_link_libraries(${PROJECT_NAME} wsock32 ws2_32)
endif()


set(compiler_flags_gcc
  -Werror
  -Wall
  -Wextra
  -Wsign-conversion
  -Wsign-compare
  -Wfloat-equal
  -Wunused-value
  -Wunused-but-set-variable
  -Wtype-limits
  -Wshadow
  -Wconversion-null
  -pedantic
  -Wcast-align
  -Wcast-qual
  -Wformat
  -Wformat-nonliteral
  -Wformat-security
  -Winit-self
  -Wuninitialized
  -Wmissing-declarations
  -Wlogical-op
  -Wmissing-include-dirs
  -Wold-style-cast
  -Wpointer-arith
  -Wunreachable-code
  -Wnormalized=nfc
  -Wwrite-strings
  -Wvla
  -fstrict-aliasing
  -Wstrict-overflow=2
  -Woverloaded-virtual
  -Wsign-promo
  -ffunction-sections
  -fdata-sections
  ${GCC_RELEASE_OPTIMIZATION_LEVEL}
)

set(compiler_flags_msvc
  /W4
  /WX
  /w44060
  /w44063
  /w44065
  /w45204
  /w45205
  /w44181
  /w44203
  /w44301
  /w44303
  /w44318
  /w44327
  /w44328
  /w44413
  /w44482
  /w44854
  /w45054
  /w45055
  /w45056
  /w45062
  /w45219
)
find_package(GTest QUIET)

if(GTEST_FOUND AND CMAKE_BUILD_TYPE STREQUAL "Debug" AND CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  set(compiler_flags_gcc ${compiler_flags_gcc} -fprofile-arcs -ftest-coverage)
  target_link_libraries(${PROJECT_NAME} gcov)
endif()

if ("${CMAKE_CXX_COMPILER_ID}" STREQUAL "GNU")
set_source_files_properties(src/MD5.cpp PROPERTIES COMPILE_FLAGS "-Wno-old-style-cast -Wno-sign-conversion")
set_source_files_properties(src/SHA256.cpp PROPERTIES COMPILE_FLAGS "-Wno-old-style-cast -Wno-cast-qual")
  target_compile_options(${PROJECT_NAME} PRIVATE ${compiler_flags_gcc})
elseif ("${CMAKE_CXX_COMPILER_ID}" STREQUAL "MSVC")
  set_source_files_properties(src/MD5.cpp PROPERTIES COMPILE_FLAGS "-D _CRT_SECURE_NO_WARNINGS /wd4267")
  target_compile_options(${PROJECT_NAME} PRIVATE ${compiler_flags_msvc})
endif()

if(GTEST_FOUND)
enable_testing()
add_subdirectory(${PROJECT_SOURCE_DIR}/tests)
else()
message(STATUS "GTest not found. Tests are not built")
endif()
