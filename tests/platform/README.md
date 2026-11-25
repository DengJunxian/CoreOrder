# Member C Standalone Runtime Tests (`tests/runtime`)

This standalone CMake project builds Member C's production static library (`native/runtime/executor.cpp`) together with C1–C3 module tests and a diagnostic module microbenchmark against the pinned Taskflow v3.11.0 submodule (`vendor/taskflow`, SHA `816b4ad53b44196c88f409eb7b4a25a0e3bfdf42`) and the public R4-v1 ABI header (`include/coreorder/contracts.hpp`).

## Test Double Scope

Because Member B's production `native/fcn/evaluate.cpp` and Member D's production layout packer are integrated centrally by the team leader (`INTEGRATION_PENDING`), `fcn_test_fixture.hpp` provides an explicitly marked **module-level test double** (`evaluate_range_test_double` and `pack_soa_test_double`) that loads real PAMS FCN rows from `fixtures/pams/fcn/rows.jsonl` and verifies exact IEEE-754 hex outputs before testing Taskflow partitioning and multi-worker determinism. It is never shipped as production FCN code.

## Build & Run (GCC / Clang / MinGW-w64)

```bash
cmake -S tests/runtime -B build/runtime -DCMAKE_BUILD_TYPE=Release
cmake --build build/runtime -j4
ctest --test-dir build/runtime --output-on-failure -V
```

On Windows with MinGW-w64 (e.g. `D:\CodeBlocks\MinGW\bin` on `PATH`), use `-G Ninja` (recommended, especially if the repo path contains non-ASCII characters):

```powershell
cmake -S tests/runtime -B build/runtime -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/runtime -j4
ctest --test-dir build/runtime --output-on-failure -V
```

## Module-Level Diagnostic Microbenchmark

```bash
./build/runtime/runtime_microbench fixtures/pams/fcn/rows.jsonl
```

This microbenchmark measures hot pre-packed C++ scheduling and test-double numeric evaluation only; it is **not** a formal end-to-end CoreOrder system benchmark.
