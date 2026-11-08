cmake_minimum_required(VERSION 3.20)
project(ZoeTrinityNative LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(trinity_core STATIC
    native/json.cpp
    native/sha256.cpp
    native/trinity_core.cpp
)
target_include_directories(trinity_core PUBLIC native)
if(MSVC)
    target_compile_options(trinity_core PRIVATE /W4)
else()
    target_compile_options(trinity_core PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_executable(trinity_core_tests native/tests.cpp)
target_link_libraries(trinity_core_tests PRIVATE trinity_core)

if(WIN32)
    add_executable(ZoeTrinity WIN32 native/win_main.cpp native/http_server.cpp)
    target_link_libraries(ZoeTrinity PRIVATE trinity_core ws2_32 comdlg32 gdi32 user32)
    if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
        target_link_options(ZoeTrinity PRIVATE -static -static-libgcc -static-libstdc++)
        target_link_options(trinity_core_tests PRIVATE -static -static-libgcc -static-libstdc++)
    endif()
endif()

enable_testing()
add_test(NAME trinity_core_tests COMMAND trinity_core_tests)
