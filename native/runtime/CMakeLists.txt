cmake_minimum_required(VERSION 3.20)

get_filename_component(COREORDER_RUNTIME_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
find_package(Threads REQUIRED)

if(NOT TARGET coreorder_runtime)
    add_library(coreorder_runtime STATIC
        executor.cpp
    )
    set_target_properties(coreorder_runtime PROPERTIES
        POSITION_INDEPENDENT_CODE ON
        CXX_STANDARD 17
        CXX_STANDARD_REQUIRED ON
        CXX_EXTENSIONS OFF
    )
    target_include_directories(coreorder_runtime
        PUBLIC
            "${COREORDER_RUNTIME_ROOT}/include"
            "${CMAKE_CURRENT_SOURCE_DIR}"
    )
    target_include_directories(coreorder_runtime SYSTEM PRIVATE
        "${COREORDER_RUNTIME_ROOT}/vendor/taskflow"
    )
    target_link_libraries(coreorder_runtime
        PUBLIC
            Threads::Threads
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(coreorder_runtime PRIVATE
            -fno-fast-math
            -ffp-contract=off
            -Wall
            -Wextra
            -Werror
        )
    endif()
endif()
