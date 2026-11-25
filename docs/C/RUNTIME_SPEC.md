# CoreOrder 成员 C 运行时规格与 `run_ranges` 契约 (`RUNTIME_SPEC`)

- **角色**：成员 C（确定性多核执行与任务粒度负责人）
- **契约版本**：`coreorder-r4-v1`
- **基线来源**：`origin/codex/g0-candidate@f867a4fb07c928f459fa8b6d3e84a95ee88b1742`
- **继承上游与许可**：
  - Taskflow v3.11.0（MIT，`vendor/taskflow`，固定 SHA `816b4ad53b44196c88f409eb7b4a25a0e3bfdf42`）
  - PAMS v0.3.0 剩余名额安全批次思想（EPL-1.0，`vendor/pams/pams/runners/agent_parallel.py`，固定 SHA `6cd53810103780770c5b5d6ee0069ccab9f4b358`）
  - CoreOrder 公共 ABI（EPL-1.0，`include/coreorder/contracts.hpp`）

---

## 1. 设计目标与边界

成员 C 负责在 **GIL 释放的纯 C++ 数值执行段** 中，以**确定性、可复用、低调度开销**的方式并行调度半开行区间 `[0, rows)`，并严格将**物理线程完成次序**与**金融事件/订单提交次序**解耦。

- **C 负责**：持久 `tf::Executor` 生命周期、静态/动态区间分块、覆盖 `[0, rows)` 恰好一次、任务级异常汇合与确定性传播、非重入保护、调度诊断指标（`actual_workers`、`task_count`、`rows`、`used_taskflow`）及外围 BLAS/OpenMP 嵌套线程审计。
- **C 不负责（严禁越界）**：不实现 FCN 数值公式（归 B）、不实现 AoS/SoA 打包（归 D）、不修改市场/订单簿/安全批次抽样/Python RNG（归 A）、不持有或回调任何 `py::object` 或 Python RNG。

---

## 2. Taskflow v3.11.0 固定 API 审计（C1）

经实读 `vendor/taskflow/taskflow/taskflow.hpp`、`core/executor.hpp`、`algorithm/for_each.hpp`、`algorithm/partitioner.hpp` 与 `utility/iterator.hpp`：

1. **版本宏校验**：`native/runtime/executor.cpp` 在编译期静态断言 `static_assert(TF_VERSION == 301100)`，严禁误用 Taskflow v4 新增接口或未锁定版本。
2. **真实使用的 v3.11.0 API**：
   - `tf::Executor(size_t N)`、`executor.num_workers()`、`executor.run(flow).get()`、`~Executor()`（自动 `wait_for_all` 并 join 全部 worker）。
   - `tf::Taskflow::for_each_by_index(tf::IndexRange<std::size_t>(0, rows, 1), callback, partitioner)`。
   - `tf::StaticPartitioner(grain)`（默认静态分块）与 `tf::DynamicPartitioner(grain)`（同框架可选对照）。
3. **v3.11.0 异常机制关键发现**：
   - `make_for_each_by_index_task` 在 `W > 1 && N > chunk_size` 时通过 `rt.silent_async` 派生子任务；而 `core/executor.hpp:1876` 中，无外部锚点的 `silent_async` 异常可能只滞留在节点本身，且多任务并发抛异常时首个到达线程具有非确定性。
   - 因此 `NativeExecutor::run_ranges` 在每个子区间闭包内显式捕获 `std::current_exception()`，按**最小 `begin` 索引**确定性记录最早失败异常，并始终等待 `executor_->run(flow).get()` 完整汇合所有 worker 后再重新抛出。

---

## 3. 生产接口签名（`native/runtime/executor.hpp`）

```cpp
namespace coreorder::runtime {

enum class Schedule : std::int32_t {
    static_partition = 0,
    dynamic_partition = 1,
};

struct RunStats {
    std::size_t requested_workers = 1;
    std::size_t actual_workers = 1;
    std::size_t rows = 0;
    std::size_t grain = 0;
    Schedule schedule = Schedule::static_partition;
    std::size_t task_count = 0;
    bool used_taskflow = false;
};

using RangeTask = std::function<void(std::size_t begin, std::size_t end)>;

// native-serial：绝不构造 tf::Executor，直接同步执行 [0, rows)
RunStats run_serial(std::size_t rows, const RangeTask& task);

template <typename Kernel>
RunStats evaluate_serial(const InputView& input, OutputView output, Kernel&& kernel);

class NativeExecutor {
public:
    explicit NativeExecutor(std::size_t workers); // workers == 0 抛 std::invalid_argument
    ~NativeExecutor() noexcept;                   // 析构时 join 全部 worker

    NativeExecutor(const NativeExecutor&) = delete;
    NativeExecutor& operator=(const NativeExecutor&) = delete;

    std::size_t requested_workers() const noexcept;
    std::size_t actual_workers() const noexcept;
    std::size_t batches_executed() const noexcept;
    std::uint64_t total_tasks_executed() const noexcept;
    std::uint64_t total_rows_executed() const noexcept;

    RunStats run_ranges(
        std::size_t rows,
        std::size_t grain,
        Schedule schedule,
        const RangeTask& task);

    template <typename Kernel>
    RunStats evaluate_ranges(
        const InputView& input,
        OutputView output,
        std::size_t grain,
        Schedule schedule,
        Kernel&& kernel);
};

std::shared_ptr<NativeExecutor> make_persistent_executor(std::size_t workers);

}  // namespace coreorder::runtime
```

---

## 4. 生命周期、边界与错误传播协议

| 维度 | 契约规定 | 实现保障 |
| :--- | :--- | :--- |
| **执行器生命周期** | 单次 simulation run 初始化创建一次，跨全部 step/batch 持久复用，run 结束时 join 并销毁 | `NativeExecutor` 不可拷贝/移动；析构调用 `tf::Executor::~Executor()` 完整 join；禁止每 step 新建线程池 |
| **`native-serial` vs `p1`** | `native-serial` 为直接循环；`native-parallel, workers=1` 仍走 Taskflow 以隔离调度开销 | `run_serial` 绝不构造 `tf::Executor`（`used_taskflow=false`）；`NativeExecutor(1)` 对非空批次走 `tf::Executor(1)`（`used_taskflow=true`） |
| **空批次 (`rows == 0`)** | 立即返回，不访问空指针，不调度任务 | 返回 `task_count=0, used_taskflow=false`，允许 `data == nullptr` |
| **非法参数** | 派发任何任务前立即拒绝 | `workers == 0`、`grain == 0`、未知 `Schedule`、空 `RangeTask`、视图长度不等或非空视图含 `nullptr` 均抛 `std::invalid_argument` |
| **异常传播与汇合** | 任一任务抛异常时，必须等待全部在途 worker 退出缓冲区访问后再向外传播 | `executor_->run(flow).get()` 形成硬汇合屏障；若多个区间抛异常，确定性重抛最小 `begin` 处的异常；调用方恢复 GIL 后整批中止且不回填部分订单 |
| **并发重入** | 同一执行器实例不允许并发/递归重入 | `InFlightGuard` 原子标志检测重入，立即抛 `std::runtime_error` 且不死锁，并在异常展开后自动复位 |

---

## 5. 确定性证明前提（C1/C3）

调度层保证**输出数组逐字节与线程数、分块粒度、静态/动态调度无关**，严格依赖以下 4 条前提（全部已写入契约边界）：

1. **输入只读不变**：所有 worker 并发读取同一份稳定的 `InputView`（AoS 或 SoA），整个 `run_ranges` 期间调用方保持缓冲区 owner 存活且不 resize、不写入。
2. **输出单写者与恰好一次覆盖**：划分出的半开区间 `[begin, end)` 两两不相交、满足 `RowRange{begin, end}.valid_for(rows)`，并集恰好等于 `[0, rows)`；每个输出槽 `output.data[i]` 在整个批次内仅被唯一任务写入一次。
3. **无共享归约与无外部副作用**：worker 内部不读写共享可变状态（无原子 ID 分配、无跨行浮点累加归约、无 RNG 推进、无 Python/GIL 回调）。
4. **严格汇合后原序消费**：`run_ranges` 在 `executor_->run(flow).get()` 完整汇合后才返回；Python 侧（A 负责）按原行序 `0 .. rows-1` 与原 agent/market 归组回填订单并调用上游 `_check_submitted_orders` / `_handle_orders`。外部抽样顺序、剩余名额安全批次与各 agent 的 Python PRNG 状态完全由 A 维护。
