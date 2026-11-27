cmake_minimum_required(VERSION 3.20)
project(CoreOrder LANGUAGES CXX)

add_library(coreorder_contracts INTERFACE)
target_include_directories(coreorder_contracts INTERFACE "${CMAKE_CURRENT_SOURCE_DIR}/include")
target_compile_features(coreorder_contracts INTERFACE cxx_std_17)

find_package(Python 3.12...<3.13 REQUIRED COMPONENTS Interpreter Development.Module)
set(PYBIND11_FINDPYTHON ON)
add_subdirectory(vendor/pybind11 EXCLUDE_FROM_ALL)
add_subdirectory(native/runtime)

pybind11_add_module(_coreorder_fcn NO_EXTRAS
    native/coreorder_module.cpp
    native/bindings/fcn_binding.cpp
    native/fcn/evaluate.cpp
)
target_include_directories(_coreorder_fcn PRIVATE native/bindings)
target_link_libraries(_coreorder_fcn PRIVATE coreorder_contracts coreorder_runtime)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(_coreorder_fcn PRIVATE -fno-fast-math -ffp-contract=off)
elseif(MSVC)
    target_compile_options(_coreorder_fcn PRIVATE /fp:strict)
else()
    message(FATAL_ERROR "The FCN serial extension requires a supported strict floating-point compiler")
endif()

include(CTest)
if(BUILD_TESTING)
    find_package(Threads REQUIRED)

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

    foreach(test_name IN ITEMS c2_executor_test c3_determinism_test)
        add_executable(${test_name} tests/platform/${test_name}.cpp native/fcn/evaluate.cpp)
        target_link_libraries(${test_name} PRIVATE coreorder_runtime)
        target_compile_features(${test_name} PRIVATE cxx_std_17)
        target_compile_definitions(${test_name} PRIVATE
            COREORDER_FIXTURE_PATH="${CMAKE_CURRENT_SOURCE_DIR}/fixtures/pams/fcn/rows.jsonl")
        if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
            target_compile_options(${test_name} PRIVATE -fno-fast-math -ffp-contract=off)
        elseif(MSVC)
            target_compile_options(${test_name} PRIVATE /fp:strict)
        endif()
        add_test(NAME ${test_name} COMMAND ${test_name})
    endforeach()

    add_executable(coreorder_layout_abi tests/layout/abi_check.cpp)
    target_link_libraries(coreorder_layout_abi PRIVATE coreorder_contracts)
    add_test(NAME layout_abi COMMAND "${Python_EXECUTABLE}"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/layout/compare_abi.py" $<TARGET_FILE:coreorder_layout_abi>)
    foreach(replay IN ITEMS replay_binding replay_live_event)
        add_test(NAME layout_${replay}
            COMMAND "${CMAKE_COMMAND}" -E env "PYTHONPATH=$<TARGET_FILE_DIR:_coreorder_fcn>"
            "${Python_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/layout/${replay}.py"
            "${CMAKE_CURRENT_SOURCE_DIR}/fixtures/pams")
    endforeach()
endif()
