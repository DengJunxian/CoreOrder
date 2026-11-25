# 成员 C 研究记录与机制诊断 (`RESEARCH`)

## 1. 上游源码与调度边界审计

### 1.1 PAMS 现有安全批次（`vendor/pams/pams/runners/agent_parallel.py`）
精读 `MultiThreadAgentParallelRunner._collect_orders_from_normal_agents`（L937–L1055）：
- PAMS 已通过“按剩余名额 `n_remaining = max_normal_orders - n_orders` 分批抽取 agent”来保持与 `SequentialRunner` 相同的调用集合与早停语义；若批内存在返回空订单列表的 agent，再按相同顺序补抽下一批。
- 原版 `MultiThreadAgentParallelRunner` 在 Python 侧执行 `agent.submit_orders`，受 CPython GIL 制约无法加速纯数值 CPU 计算；而 `MultiProcessAgentParallelRunner` 每次任务需 pickle/unpickle 整个仿真对象图（注释 L1135 明确指出 1000 个 FCN agent 约 4 MB 且耗时数十毫秒）。
- **对 CoreOrder 的启示**：安全批次窗口本身属于上游已确立思想（不归为本项目原创）；成员 C 的工作是在**移出 GIL 后的 C++ 数值行层面**，复用成熟的 Taskflow v3.11.0 持久执行器承接每批 `[0, rows)`，把执行器开销与并行边界测清。

### 1.2 Taskflow v3.11.0 实现细节审计（`vendor/taskflow`）
精读 `taskflow/algorithm/for_each.hpp`、`algorithm/partitioner.hpp`、`core/executor.hpp`、`utility/iterator.hpp`：
- `StaticPartitioner(chunk_size)` 将 `[0, N)` 按 `chunk_size` 切分为互不相交的半开区间，以 `stride = W * chunk_size` 轮转分配给 `W` 个 worker；当 `W <= 1 || N <= chunk_size` 时退化为单次调用 `c(r)`，但仍通过 `tf::Executor` 的 worker 线程调度并 join。
- `DynamicPartitioner(chunk_size)` 通过共享 `std::atomic<size_t>` 的 `fetch_add(chunk_size, relaxed)` 动态领取半开区间。
- **关键工程发现（异常处理）**：`make_for_each_by_index_task` 内部以 `rt.silent_async` 派生子任务，而 `Executor::_process_exception`（L1876）对无外部锚点的 `silent_async` 仅将异常暂存于节点，且多线程并发抛异常时首个到达的异常取决于物理竞态。
- **工程对策**：`NativeExecutor::run_ranges` 在子区间闭包内显式捕获异常并按最小 `begin` 归并，且在 `executor_->run(flow).get()` 完整汇合所有 worker 后才重新抛出。我们在 `c3_determinism_test` 中构造了“较晚区间 `begin=320` 立即抛异常、较早区间 `begin=128` 延迟 5 ms 抛异常、健康区间 `begin=0` 延迟 15 ms 完成”的竞争场景，实测验证：
  1. 异常到达调用方时，在途活跃任务数 `active_tasks == 0`（无悬空缓冲区访问）；
  2. 静态与动态两种调度下均确定性抛出 `injected_error_at_128`；
  3. 异常结束后 `in_flight_` 守卫复位，同一 `NativeExecutor` 实例保持干净状态。

---

## 2. 模块级诊断微基准观测（非正式端到端结论）

> **测量范围声明**：本节数据来自 `tests/runtime/runtime_microbench.cpp`（原始 JSON 见 [evidence/c_microbench.json](evidence/c_microbench.json)），在热缓存、预打包 AoS 输入及成员 C 的 FCN 测试替身上测量纯 C++ 区间调度与计算时间（5 次 warmup + 25 次计时取中位数）。**不包含** Python RNG 采样、AoS/SoA 打包、Python `Order` 回建与串行撮合，因此**不是**正式端到端系统性能结论。

测试主机：Windows 11 x86-64，AMD64（32 逻辑核），MinGW-w64 GCC 14.2.0 (`-O3 -fno-fast-math -ffp-contract=off`)，24 条真实 PAMS `rows.jsonl` 平铺扩展。

| 行数 `rows` | `native-serial` (µs) | `p1` static g=128 (µs) | `p2` static g=128 (µs) | `p4` static g=128 (µs) | `p8` static g=128 (µs) | 核内观测摘要 |
| ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 24 | 0.700 | 7.100 | 8.800 | 8.700 | 11.400 | 调度开销 (~6.4 µs) 远超计算本身，`p1` 慢 10.1× |
| 128 | 4.300 | 11.300 | 8.900 | 16.200 | 15.200 | `rows <= grain` 仅 1 个任务，多核无收益反增开销 |
| 1024 | 21.600 | 27.500 | 27.800 | 14.600 | 21.800 | **收益交叉点附近**：`p4` 达 1.48×，`p8` 因 8 线程同步抖动回落至 0.99× |
| 16384 | 355.500 | 369.800 | 259.400 | 118.900 | 145.200 | `p4` 达 2.99×（`dynamic g=128` 106.5 µs，3.34×） |
| 65536 | 1428.100 | 1481.200 | 762.100 | 408.200 | 482.600 | `p4` 达 3.50×（`dynamic g=32` 405.8 µs，3.52×）；`p8` 受 Windows 唤醒抖动影响中位数不如 `p4`（min 221.4 µs） |

### 初步机制解释（待 G3 冻结后在正式主机系统级复验）
1. **固定调度门槛（`p1 - native-serial`）**：即使线程池已持久复用、不重建线程，单次 `tf::Taskflow` 构建、提交、唤醒与 `future.get()` 汇合在当前 Windows 主机仍引入约 **6–14 µs** 的固定开销。在真实金融市场中，当 `maxNormalOrders` 很小（如 M=1 或空补批长尾收缩后的窄批次）时，多核调度必然产生负收益。
2. **为什么 `native-parallel, workers=1` 不能替代 `native-serial`**：实测 `rows=24` 时 `native-serial` 为 0.7 µs 而 `p1` 为 7.1 µs，`rows=65536` 时两者分别为 1428.1 µs 与 1481.2 µs。分离这两组对照能够干净地剥离“C++ 脱离 GIL 收益”与“Taskflow 调度代价”。
3. **粒度与静态/动态差异**：在 `rows=1024, p4` 时 `dynamic g=32`（26.6 µs）明显慢于 `static g=32`（14.2 µs），体现了细粒度下共享原子计数器 `fetch_add` 的竞争成本；在 `rows=16384/65536` 且存在 OS 调度抖动时，动态分块有助于掩盖个别线程被抢占导致的尾延迟，中位数与尾部方差优于粗粒度静态分块。
4. **外围库嵌套线程风险**：实测本机默认未设置 `OMP_NUM_THREADS` / `OPENBLAS_NUM_THREADS` 等 6 个变量（`oversubscription_risk=true`），正式实验必须在环境准备阶段显式冻结为 `1` 并记入 `environment.json`。

---

## 3. 工程构建与跨平台记录

- **Windows 非 ASCII 路径问题**：在路径含中文（`大学/大二/计组`）的 Windows 主机上，`MinGW Makefiles` + `mingw32-make` 无法解析跨目录绝对路径的目标对象名。通过将 `native/runtime/CMakeLists.txt` 独立为子目录目标并使用 `-G Ninja`，实现 0 警告构建（`-Wall -Wextra -Werror`）并保持 Linux/macOS/Windows 通用。
- **TSan 限制**：MinGW-w64 GCC 14.2.0 缺少 `libtsan`（实测链接报 `cannot find -ltsan`，退出码 1），已诚实标为 `N/A`，并保留 CMake 选项 `-DCOREORDER_RUNTIME_TSAN=ON` 供 Linux 集成环境使用。
