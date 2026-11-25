# CoreOrder 成员 C 模块接入方法与依赖清单 (`INTEGRATION`)

本文件面向组长（集中集成负责人）及成员 A / B / D / E，说明如何将成员 C 的 `native/runtime/` 生产模块接入 CoreOrder 主工程与成员 B 的 pybind11 绑定。

---

## 1. 模块文件与依赖清单

### 生产文件（全部位于成员 C 白名单 `native/runtime/`）
- [native/runtime/executor.hpp](../../../native/runtime/executor.hpp)：公共头文件（`coreorder::runtime`）
- [native/runtime/executor.cpp](../../../native/runtime/executor.cpp)：Taskflow v3.11.0 持久执行器与诊断实现
- [native/runtime/CMakeLists.txt](../../../native/runtime/CMakeLists.txt)：独立可复用 CMake 目标 `coreorder_runtime`（静态库，`POSITION_INDEPENDENT_CODE ON`，可直接链接进 pybind11 共享库）

### 固定外部依赖
| 依赖 | 路径 / 目标 | 固定版本 / SHA | 许可 |
| :--- | :--- | :--- | :--- |
| Public ABI Header | `include/coreorder/contracts.hpp` | `coreorder-r4-v1`（G0 候选 `f867a4f`） | EPL-1.0 |
| Taskflow | `vendor/taskflow` | v3.11.0（`816b4ad53b44196c88f409eb7b4a25a0e3bfdf42`） | MIT |
| C++ 标准与线程库 | C++17 + `Threads::Threads` | `-O3 -fno-fast-math -ffp-contract=off` | — |

### 外部模块接口依赖（当前 `INTEGRATION_PENDING`）
| 依赖对象 | 责任人 | 所需签名 / 产物 |
| :--- | :--- | :--- |
| 唯一 FCN range 核 | B | `void coreorder::evaluate_range(const InputView&, OutputView, std::size_t begin, std::size_t end);`（`native/fcn/evaluate.cpp`） |
| Python 绑定与 GIL 边界 | B | `coreorder::binding::bind_fcn(module, factory)`（`native/bindings/fcn_binding.hpp`） |
| 生产 AoS/SoA 打包与对齐校验 | D | 满足 `coreorder-r4-v1` 112B/16B ABI 与对齐约束的连续输入 buffer |
| 安全批次、RNG、订单回填与根 CMake | A | 根 `CMakeLists.txt` 接入 `add_subdirectory(native/runtime)`；runner 按单次 run 创建并复用一个并行实例 |
| 独立整机差分验证 | E | 同 seed、多 `workers` / `grain` / 两 layout 与上游 `py-seq/upstream` 全轨迹比对（G2） |

---

## 2. 根 CMakeLists 接入方法（交由 A 执行）

在根目录 `CMakeLists.txt` 中添加一行即可获得静态库目标 `coreorder_runtime`：

```cmake
add_subdirectory(native/runtime)
# 将 coreorder_runtime 链接到最终的 pybind11 扩展模块：
# target_link_libraries(_coreorder_fcn PRIVATE coreorder_runtime)
```

> **Windows 非 ASCII 路径提醒**：在包含中文目录的 Windows MinGW-w64 环境下，推荐使用 `-G Ninja` 而非 `MinGW Makefiles`；`native/runtime/CMakeLists.txt` 将 `executor.cpp` 作为子目录本地源文件编译，确保目标对象路径为纯 ASCII。

---

## 3. 接入成员 B `ExecutorFactory` 的示例代码

成员 B 在 `docs/roles/B/INTEGRATION.md` 中预留的工厂契约为：

```cpp
// 来自成员 B 的 native/bindings/fcn_binding.hpp
using RangeTask = std::function<void(std::size_t begin, std::size_t end)>;
using RangeExecutor = std::function<void(std::size_t rows, std::size_t grain,
                                         Schedule schedule, const RangeTask& task)>;
using ExecutorFactory = std::function<RangeExecutor(std::size_t workers)>;
```

组长在生产扩展模块初始化点（如 `native/bindings/module.cpp`）仅需约 12 行薄胶水即可将成员 C 接入成员 B（零额外拷贝、零 Python 回调）：

```cpp
#include "executor.hpp"
#include "fcn_binding.hpp"

namespace {

coreorder::runtime::Schedule map_schedule(coreorder::binding::Schedule s) {
    using BS = coreorder::binding::Schedule;
    using CS = coreorder::runtime::Schedule;
    switch (s) {
        case BS::static_partition:  return CS::static_partition;
        case BS::dynamic_partition: return CS::dynamic_partition;
    }
    throw std::invalid_argument("unknown binding schedule");
}

coreorder::binding::RangeExecutor make_coreorder_executor(std::size_t workers) {
    // 单次 Evaluator / simulation run 生命周期内持久持有同一个 NativeExecutor
    auto persistent = coreorder::runtime::make_persistent_executor(workers);
    return [persistent](std::size_t rows,
                        std::size_t grain,
                        coreorder::binding::Schedule schedule,
                        const coreorder::binding::RangeTask& task) {
        (void)persistent->run_ranges(rows, grain, map_schedule(schedule), task);
    };
}

}  // namespace

// 在 PYBIND11_MODULE 初始化函数中：
// coreorder::binding::bind_fcn(module, &make_coreorder_executor);
```

### 纯 C++ 侧直调示例（可选，用于原生联调与基准）

```cpp
#include <coreorder/contracts.hpp>
#include "executor.hpp"

// native-serial（不创建线程池）：
auto s_stats = coreorder::runtime::evaluate_serial(
    input_view, output_view, coreorder::evaluate_range);

// native-parallel（持久复用，每 run 创建一次）：
coreorder::runtime::NativeExecutor exec(workers);
for (/* each safe batch in simulation */) {
    auto p_stats = exec.evaluate_ranges(
        input_view, output_view, grain,
        coreorder::runtime::Schedule::static_partition,
        coreorder::evaluate_range);
}
```

---

## 4. 外围数值库嵌套线程检查（C3）

在启动多核仿真或正式基准前，A/E 可调用 `coreorder::runtime::detect_nested_threading_env()` 或在运行进程环境设置 `recommended_single_thread_blas_env()` 返回的 6 个环境变量均为 `"1"`：
`OMP_NUM_THREADS=1`、`OPENBLAS_NUM_THREADS=1`、`MKL_NUM_THREADS=1`、`BLIS_NUM_THREADS=1`、`VECLIB_MAXIMUM_THREADS=1`、`NUMEXPR_NUM_THREADS=1`，避免 NumPy/SciPy 底层 BLAS 与 Taskflow worker 发生 oversubscription。

---

## 5. 集成验收方法（交组长与 E 执行）

待 A/B/C/D 合并联调后，按 [08_Integration_Acceptance.md](../../gates/G0.md) 与 R4 G2 标准执行以下检查：

1. **生产绑定替换测试替身**：确认扩展模块链接真实 `coreorder_runtime` + 真实 `native/fcn/evaluate.cpp`，不再依赖 `tests/runtime/fcn_test_fixture.hpp` 或 B 的 `std::async` 替身。
2. **线程与调度一致性（G2 硬门）**：在相同 workload、seed、`book_restore` 下对比 `py-seq/upstream`、`native-serial`、`native-parallel (workers=1/2/4, static/dynamic, grain=32/128)`、`AoS/SoA`，校验逐事件日志、逐 step 状态、订单价格 `float.hex()` 及最终完整 RNG 状态（含 gauss 缓存）完全一致。
3. **生命周期与边界核查**：确认单次 run 仅构造一次 `NativeExecutor`（`batches_executed()` 递增）、0 行/1 行/尾块/M=1/空补批/HFT 插入均正确、单行数值错误或 C++ 异常在完整 join 后于 GIL 恢复段向上抛出且不回填部分订单。
4. **Linux 主机补充 TSan**：本机 Windows MinGW-w64 缺少 `libtsan`（已实测标 `N/A`），集成阶段在 Linux GCC/Clang 主机可开启 `-DCOREORDER_RUNTIME_TSAN=ON` 补跑一次 `tests/runtime` 并发检查（仅用于正确性，绝不用于正式计时）。
