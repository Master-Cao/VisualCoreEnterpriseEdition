cmake_minimum_required(VERSION 3.16)
project(sick_visionary_cpp_shared_tests)

set(PRIVATE_SOURCES
  src/CoLa2ProtocolHandlerTest.cpp
  src/MockTransport.cpp
  src/main.cpp
  src/VisionaryTMiniDataTest.cpp
)

add_executable(${PROJECT_NAME} ${PRIVATE_SOURCES})

if(CMAKE_BUILD_TYPE STREQUAL "Debug" AND CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  set(compiler_flags_gcc ${compiler_flags_gcc} -fprofile-arcs -ftest-coverage)
  target_link_libraries(${PROJECT_NAME} gcov)
endif()


if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  set_target_properties(${PROJECT_NAME} PROPERTIES LINK_FLAGS_RELEASE -s)
  target_compile_options(${PROJECT_NAME} PRIVATE ${compiler_flags_gcc})
endif()

target_include_directories(${PROJECT_NAME} PRIVATE ${PROJECT_SOURCE_DIR}/src)
target_link_libraries(${PROJECT_NAME} sick_visionary_cpp_shared GTest::gtest GTest::gtest_main)


gtest_discover_tests(${PROJECT_NAME} XML_OUTPUT_DIR ${CMAKE_BINARY_DIR}/tests)
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
add_test(NAME coverage COMMAND gcovr --root "${CMAKE_SOURCE_DIR}" --exclude "${CMAKE_SOURCE_DIR}/3pp/.*" --exclude-unreachable-branches --print-summary --xml-pretty -o coverage.xml)
endif()