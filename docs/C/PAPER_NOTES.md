# 成员 C 论文方法与答辩素材草稿 (`PAPER_NOTES`)

> 本稿覆盖 C1–C3 已完成的运行时机制、确定性证明框架与模块诊断边界；正式端到端多核曲线与整机 Amdahl 分解将在 G3 冻结及 C4 正式采数后补入，严禁将本文中的模块微基准直接写成端到端加速结论。

---

## 1. 论文方法段落草稿：确定性多核执行与任务粒度控制

### 1.1 并行窗口与依赖分离
在 PAMS 多智能体仿真中，单个仿真步内的普通 FCN 交易者决策与后续订单撮合具有本质不同的数据依赖：同一市场观测快照下，待激活普通交易者的纯数值决策彼此独立，而订单进入订单簿后的价时优先撮合、账户现金/持仓更新及市场事件回调则构成严格的因果序（Fujimoto, 1990）。PAMS 上游的 `MultiThreadAgentParallelRunner` 已提出按“剩余名额（remaining quota）”构造安全批次的方法，确保被调用的普通交易者集合与 `SequentialRunner` 一致。然而，原版 Python 多线程受制于 CPython GIL，无法并行执行纯数值计算；多进程则因每批需序列化完整仿真对象图而引入高昂通信开销。

CoreOrder 保留上游安全批次与原提交顺序语义，不重新发明任务调度算法，而是将纯数值决策段移出 GIL，基于固定版本 Taskflow v3.11.0（Huang et al., TPDS）构建持久原生执行器 `NativeExecutor`，将**物理线程调度次序**与**逻辑金融事件次序**彻底隔离。

### 1.2 确定性保证的四个结构性前提
CoreOrder 并不依靠对共享订单簿加锁或对异步输出重新排序来“事后凑一致”，而是通过数据依赖约束在结构上保证调度无关的逐字节确定性：
1. **输入不可变**：主线程在持 GIL 阶段完成所有 Python PRNG 抽样（保留每名交易者自身的 `random.Random` 与 `gauss` 缓存）和数值缓冲准备；GIL 释放后，全部 worker 线程仅只读访问稳定的 `InputView`（AoS 或 SoA）。
2. **区间划分与输出单写者**：Taskflow 的 `for_each_by_index` 配合 `StaticPartitioner(grain)`（及同框架可选 `DynamicPartitioner(grain)`）将 `[0, n)` 划分为两两不相交的半开区间 `[begin, end)`，覆盖 `[0, n)` 恰好一次。每个任务仅调用成员 B 提供的唯一 `evaluate_range` 核并独占写入 `output[begin .. end)`，不存在共享可变状态、原子 ID 分配或跨线程浮点归约。
3. **硬汇合屏障与确定性异常传播**：每次 `run_ranges` 均在 `executor.run(flow).get()` 完成全部任务汇合后才返回；若任一子任务抛出异常，执行器按最小 `begin` 索引确定性记录最早失败异常，并在所有在途 worker 退出缓冲区访问后再向外抛出，确保调用方恢复 GIL 后整批中止、绝不提交部分订单。
4. **原序消费**：汇合返回后，主线程严格按行号 `0 .. n-1` 恢复各交易者的订单列表并交回 PAMS 原有 `_check_submitted_orders` 与 `_handle_orders`。

### 1.3 执行器生命周期与开销隔离设计
为避免每仿真步重复创建/销毁操作系统线程，`NativeExecutor` 在单次仿真运行初始化时创建一次，在全运行期跨批次持久复用，并于运行结束时统一汇合销毁。同时，系统在实验设计上显式区分三种执行路径：
- `native-serial`：直接调用 `run_serial` 顺序执行 `[0, n)`，**不构造**任何 `tf::Executor`；
- `native-parallel (workers=1)`：通过单线程 `tf::Executor(1)` 提交并汇合任务，专门用于量化 Taskflow 运行时的固定调度代价；
- `native-parallel (workers > 1)`：在不同物理核数与块粒度 `grain` 下研究核内加速与串行占比的平衡（Amdahl, 1967）。

---

## 2. 答辩核心问题预案（初稿，待 C4 正式数据补全）

1. **为什么“加锁”不等于“确定性”？**
   - 互斥锁只能避免数据竞争（data race），无法约束线程抢占顺序；如果多个线程持锁向共享列表追加订单或推进共享 RNG，不同线程抢锁顺序会直接改变订单提交顺序和价格轨迹。CoreOrder 通过“主线程预采样 RNG + 只读输入 + 按行号独占输出槽 + join 后原序消费”消除了并发写共享状态的需求。
2. **为什么输出槽不需要原子 ID？**
   - 每个 `InputRow` 在打包阶段已绑定唯一的逻辑行号 `i ∈ [0, n)`，对应的 `metadata[i]`（`agent_id, market_id, call_index`）在调度前已确定；每个任务仅写 `output[i]`，真正进入订单簿所需的 `order_id` 仍在主线程串行提交阶段由 PAMS 原有逻辑分配。
3. **为什么 `native-parallel (workers=1)` 与 `native-serial` 不同？**
   - `native-serial` 是调用线程上的直接循环，无任务图构造、跨线程唤醒和 `future.get()` 同步成本；`workers=1` 仍经过 Taskflow 持久执行器。模块级诊断实测显示，在 24 行热缓冲下两者中位数相差约 6.4 µs（0.7 µs vs 7.1 µs），明确量化了调度固定门槛。
4. **为什么增加线程数或减小/增大 `grain` 反而可能变慢？**
   - 依据 Amdahl 定律与调度开销模型：当批次行数 `n` 较小（例如 `M=1` 或空补批尾批）时，核内纯计算仅微秒级，多线程唤醒与汇合开销远高于收益；`grain` 过小会放大任务切片与原子领取竞争，`grain` 过大（`grain >= n`）则退化为单任务无法利用多核；跨核数过多还会触发 OS 调度抖动、SMT 共享执行资源竞争或跨 CCX/CCD 缓存迁移。
5. **如何防止 GIL 死锁与外围库嵌套并发？**
   - 所有 Python 对象引用获取、buffer 校验与异常构造全部发生在持 GIL 阶段；Taskflow worker 只接触原生指针与标量数组，绝不调用 Python API；同一 `NativeExecutor` 禁止并发重入；通过 `detect_nested_threading_env()` 显式检查并冻结 `OMP/OPENBLAS/MKL/BLIS/VECLIB/NUMEXPR` 线程数为 1。
6. **归属声明（严格区分继承与贡献）**
   - 继承：Taskflow v3.11.0（MIT）的工作窃取调度器与分区器；PAMS v0.3.0（EPL-1.0）的安全批次与金融仿真机制。
   - 成员 C 贡献：面向 PAMS 语义约束的持久执行器封装、确定性异常汇合与重入保护、精确覆盖与边界验证套件、调度开销隔离设计及适用边界实证分析。
