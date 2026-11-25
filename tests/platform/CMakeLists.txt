cmake_minimum_required(VERSION 3.20)
project(CoreOrderRuntimeTests LANGUAGES CXX)

include(CTest)
get_filename_component(COREORDER_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
find_package(Threads REQUIRED)

option(COREORDER_RUNTIME_TSAN "Enable ThreadSanitizer if supported by toolchain" OFF)

if(NOT CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    message(FATAL_ERROR "CoreOrder runtime standalone build requires GCC or Clang strict floating-point flags")
endif()

add_library(coreorder_runtime_flags INTERFACE)
target_compile_features(coreorder_runtime_flags INTERFACE cxx_std_17)
target_compile_options(coreorder_runtime_flags INTERFACE
    -fno-fast-math
    -ffp-contract=off
    -Wall
    -Wextra
    -Werror
)
if(COREORDER_RUNTIME_TSAN)
    target_compile_options(coreorder_runtime_flags INTERFACE -O1 -g -fsanitize=thread -fno-omit-frame-pointer)
    target_link_options(coreorder_runtime_flags INTERFACE -fsanitize=thread)
endif()

# Production Member C static library (`native/runtime/`).
add_subdirectory("${COREORDER_ROOT}/native/runtime" "${CMAKE_CURRENT_BINARY_DIR}/runtime_lib")
if(COREORDER_RUNTIME_TSAN)
    target_compile_options(coreorder_runtime PRIVATE -O1 -g -fsanitize=thread -fno-omit-frame-pointer)
    target_link_options(coreorder_runtime PUBLIC -fsanitize=thread)
endif()

set(COREORDER_FCN_FIXTURE "${COREORDER_ROOT}/fixtures/pams/fcn/rows.jsonl")

# Verify A's public contract smoke compiles cleanly under the same toolchain.
add_executable(runtime_contract_smoke contract_smoke_runner.cpp)
target_include_directories(runtime_contract_smoke PRIVATE "${COREORDER_ROOT}/include")
target_compile_features(runtime_contract_smoke PRIVATE cxx_std_17)
target_compile_options(runtime_contract_smoke PRIVATE -fno-fast-math -ffp-contract=off)
add_test(NAME runtime_contract_smoke COMMAND runtime_contract_smoke)

# Stage C1: Pinned Taskflow v3.11.0 API & scheduling semantics smoke.
add_executable(c1_taskflow_smoke c1_taskflow_smoke.cpp)
target_include_directories(c1_taskflow_smoke SYSTEM PRIVATE "${COREORDER_ROOT}/vendor/taskflow")
target_compile_definitions(c1_taskflow_smoke PRIVATE COREORDER_FIXTURE_PATH="${COREORDER_FCN_FIXTURE}")
target_link_libraries(c1_taskflow_smoke PRIVATE coreorder_runtime coreorder_runtime_flags)
add_test(NAME c1_taskflow_smoke COMMAND c1_taskflow_smoke "${COREORDER_FCN_FIXTURE}")

# Stage C2: Persistent executor, static partitioning, multi-batch reuse, and view checks.
add_executable(c2_executor_test c2_executor_test.cpp)
target_compile_definitions(c2_executor_test PRIVATE COREORDER_FIXTURE_PATH="${COREORDER_FCN_FIXTURE}")
target_link_libraries(c2_executor_test PRIVATE coreorder_runtime coreorder_runtime_flags)
add_test(NAME c2_executor_test COMMAND c2_executor_test "${COREORDER_FCN_FIXTURE}")

# Stage C3: Static & Dynamic determinism, exception-join safety, re-entrancy, adapter & BLAS audit.
add_executable(c3_determinism_test c3_determinism_test.cpp)
target_compile_definitions(c3_determinism_test PRIVATE COREORDER_FIXTURE_PATH="${COREORDER_FCN_FIXTURE}")
target_link_libraries(c3_determinism_test PRIVATE coreorder_runtime coreorder_runtime_flags)
add_test(NAME c3_determinism_test COMMAND c3_determinism_test "${COREORDER_FCN_FIXTURE}")

# Module-level diagnostic microbenchmark (not formal end-to-end performance).
add_executable(runtime_microbench runtime_microbench.cpp)
target_compile_definitions(runtime_microbench PRIVATE COREORDER_FIXTURE_PATH="${COREORDER_FCN_FIXTURE}")
target_link_libraries(runtime_microbench PRIVATE coreorder_runtime coreorder_runtime_flags)
