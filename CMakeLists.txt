cmake_minimum_required(VERSION 3.20)
project(CoreOrder LANGUAGES CXX)

add_library(coreorder_contracts INTERFACE)
target_include_directories(coreorder_contracts INTERFACE "${CMAKE_CURRENT_SOURCE_DIR}/include")
target_compile_features(coreorder_contracts INTERFACE cxx_std_17)

include(CTest)
if(BUILD_TESTING)
    find_package(Python 3.12...<3.13 REQUIRED COMPONENTS Interpreter Development.Module)
    find_package(Threads REQUIRED)
    set(PYBIND11_FINDPYTHON ON)
    add_subdirectory(vendor/pybind11 EXCLUDE_FROM_ALL)

    pybind11_add_module(_coreorder_toolchain_smoke NO_EXTRAS tests/platform/toolchain_smoke.cpp)
    set_target_properties(_coreorder_toolchain_smoke PROPERTIES
        CXX_STANDARD 17
        CXX_STANDARD_REQUIRED ON
        CXX_EXTENSIONS OFF
    )
    target_include_directories(_coreorder_toolchain_smoke SYSTEM PRIVATE vendor/taskflow)
    target_link_libraries(_coreorder_toolchain_smoke PRIVATE Threads::Threads)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(_coreorder_toolchain_smoke PRIVATE -fno-fast-math -ffp-contract=off)
    endif()

    add_executable(coreorder_contract_smoke tests/platform/contract_smoke.cpp)
    target_link_libraries(coreorder_contract_smoke PRIVATE coreorder_contracts)
    set_target_properties(coreorder_contract_smoke PROPERTIES
        CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON CXX_EXTENSIONS OFF
    )
    add_test(NAME contract_smoke COMMAND coreorder_contract_smoke)

    add_test(NAME toolchain_smoke
        COMMAND "${CMAKE_COMMAND}" -E env "PYTHONPATH=$<TARGET_FILE_DIR:_coreorder_toolchain_smoke>"
            "${Python_EXECUTABLE}" -c "import _coreorder_toolchain_smoke as probe; raise SystemExit(probe.run() != 42)"
    )
endif()
