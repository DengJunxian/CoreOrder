# R5B 科研结果与证据审计

2026-11-26（上海时间）

**目标 x86 语义验收通过。G3 仍为 BLOCKED，正式性能数据为 0 条。** C01 的 420 条和 V01 的 145 条均通过，其中 V01 有 125 条生产候选回执和 20 条 PAMS 独立参考。现有证据支持报告同机确定性、堆恢复的比较工作量，以及明确标注的 pilot 机制观察。正式加速、并行效率、硬件计数差异和置信区间均缺测。

[正确性表](evidence/R5B/artifacts/validation/correctness.pdf) · [实验配置表](evidence/R5B/artifacts/validation/configuration.pdf) · [配对覆盖表](evidence/R5B/artifacts/formal-pairing-coverage.csv) · [图表和复算说明](evidence/R5B/README.md)

## 1. 数据资格与覆盖

R5B 使用 R4B 候选身份 `8113c98d7c108b8fd33dd86d35c7c63e890cf6f05fd731ded36551c26ce0219c`。华硕 WSL2 受测源码为 `58ec5764c21833142c50abacd9e2302404ffdb06`，主机 ID 为 `7fd1261e162f2fef`，实际扩展 SHA-256 为 `a9d294e6bac9098bb486d1ba3e728a0fa9f974eb858ad107fde858b86e16fc5e`。R5A 只读复验封存 V01 的原始文件、生产与独立参考的绑定，以及 timing/E05 各计划条件的资格映射。R5B 重算候选文件、验证索引中的 workload 与回执摘要，复对主机、环境、上游、二进制、配置、后端和参考 run ID，并检查候选目录、目标机运行登记与报告入口。目标机在已检查的路径仅有 pilot、C01、V01 三类批次。用真实 V01 批次进入正式报告入口，作用域检查拒绝并退出 2。

[目标机复查](evidence/R5B/x86-inventory.log) · [R5A 原始回执复验](evidence/R5A/x86-admission.json) · [C01 索引](evidence/R4B/c01-index.json) · [V01 索引](evidence/R4B/v01-index.json) · [候选锁](../../configs/experiments/r4b/protocol_lock.json)

| 实验 | 候选总数 | 预热 | 有效 | 失败 | 超时 | NOT_RUN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| H01 增量恢复 | 102 | 12 | 0 | 0 | 0 | 102 |
| E01 原版 PAMS 对照 | 85 | 10 | 0 | 0 | 0 | 85 |
| E02 原生化和多核 | 170 | 20 | 0 | 0 | 0 | 170 |
| E03 AoS/SoA | 136 | 16 | 0 | 0 | 0 | 136 |
| E05 机制诊断 | 76 | 12 | 0 | 0 | 0 | 76 |
| **合计** | **569** | **70** | **0** | **0** | **0** | **569** |

正式 timing 含 435 条测量、58 条预热。E05 含 4 条 profile、24 条 PMU、48 条 replay，其中 replay 含 12 条预热。执行锁无有效摘要且正式授权条目为空。未启动项的 run ID、实际后端、用时、热干扰和删失状态均缺测。历史 P11 W2 的两次计数超时保留原样，属于 pilot。正式批次中出现的超时须按原定驱动超时记录右删失，不能折算为完成的仿真用时。

[覆盖台账](evidence/R5A/formal-coverage.json) · [P11 超时与原始档案](../roles/A/evidence/P13/INDEX.md)

### 冻结统计口径

- 同一主机、工作负载、seed、重复和区组配对，排除预热。主指标 `simulation_s` 覆盖选择、抽样、packing、实际数值核与任务等待、订单回建、撮合、账户更新、PAMS 日志和 shutdown。独立保留 `setup_s` 和完整子进程 `process_wall_s`，两者可解释初始化与外围成本。诊断时间由对应仪器化入口解释。
- 每对计算 `log(T基线) − log(T变体)`。同 seed 的 3 对取对数比中位数，对 5 个 seed 效应取平均后指数化。围绕 5 个 seed 做 10,000 次有放回重采样，复用种子 73021，报告 95% 百分位区间。每组保留原始时间与 median/IQR。原生并行效率使用同布局、同堆底座的 direct 基线，`效率 = speedup / worker 数比`。
- H01、E01、E02、E03 分别有 3、4、8、4 项比较。每项需 15 对，目前均为 0/15，完整 seed 均为 0/5。285 个缺失配对位置包含复用的基线运行，统计独立单位始终是 seed。任一必要配对缺失时，综合 speedup、区间和效率均留空。当前各组原始时间、median、IQR 和 seed 效应也均为 NA。即使采满，五个 seed 的经验分布仍较粗，区间只刻画这批 seed 的波动，无法稳健估计尾部或跨市场普遍性。

[原定统计配置](../../configs/experiments/r4b/frozen.json) · [正式报告入口](../../analysis/report.py) · [计时契约](../CONTRACT.md) · [逐项缺测表](evidence/R5B/artifacts/formal-pairing-coverage.csv)

## 2. RQ 与证据

| 研究问题 | 现阶段证据 | 结论边界 |
| --- | --- | --- |
| RQ1 增量恢复 | x86 全轨迹差分；P11 六对堆计数；增量实现 | 已观测比较工作量减少。正式 H01 端到端效应和 Cache 归因缺测。 |
| RQ2 原生化与多核 | x86 独立参考覆盖 Python、direct 和 Taskflow；历史低开销 pilot；目标机 replay 校准 | 已验证确定性；小规模负收益与尺寸相关的 replay 表现保留。正式扩展率、效率和 Amdahl 可并行份额缺测。 |
| RQ3 内存布局 | x86 同条件 AoS/SoA 语义回执；真实输入 replay；x86 PMU 能力探针 | 校准范围内 AoS 用时更短。正式端到端布局效应、转换成本和 Cache 因果效应缺测。 |
| RQ4 瓶颈迁移 | P11 同场景阶段剖析；生产时间边界与源码审查 | 该 pilot 的恢复耗时缩小，智能体决策区段相对突出。正式 x86 阶段占比和热点迁移幅度缺测。 |

### RQ1　深簿、小恢复集合减少比较工作量

以一侧订单簿一次恢复为单位，令 `n` 为恢复后的堆大小，`k` 为暂时取出且需要恢复的存活订单数。原版拼接剩余堆与恢复订单，再执行 `heapify`，线性处理 `n` 个元素。增量路径保留剩余堆的性质，以 `heappush` 恢复这 `k` 条，其恢复的堆比较最坏为 `O(k log max(n, 2))`。这一分析只涵盖恢复，订单弹出、撮合与账本工作继续执行。符合 `k log n ≪ n` 的簿更容易获得比较工作量优势。浅簿、恢复比例较大、或恢复只占很小运行比例时，系统收益可能收窄；高比例和反转阈值缺少独立定量结果。

P11 在 Apple M5 上覆盖 3 个 workload × 2 个 pilot seed 共 6 个配对，双侧分别核对有序金融事件、工作量和恢复计数。seed 11 的浅簿 W0 两侧中位深度为 21/22，`k/n` 中位数为 9.52%/9.09%，双侧比较合计从 14,610 降至 3,286。W1-H 两侧中位深度为 423/307，比较由 1,710,577 降至 38,953。W2-H 为 925/812，比较由 8,245,535 降至 92,206。三场景双侧的 `k` 中位数均为 2。W0 提供浅簿、小规模边界对照。比较次数是算法工作量证据，采集过程带有比较器仪器化。目标 x86 的 W1-H seed 101 原版恢复和增量恢复 V01 run ID 分别为 `4d4084b6033b4b5eb8ca82c3742dd275` 和 `19fe7d05557c4fe0be3b162500a9c2d8`。

[增量撮合实现](../../src/coreorder/market_adapter.py) · [P11 两侧计数](../roles/A/evidence/P11-heap.csv) · [堆恢复机制图](../roles/A/evidence/P13/figures/heap-mechanism-pilot.pdf) · [原始计数和差分索引](../roles/A/evidence/P13/INDEX.md)

### RQ2　原生化与调度收益取决于真实批次和串行成本

E02 在相同 incremental 底座依次对照 `py-seq`、direct native、Taskflow 1/2/4 workers。direct 与 1-worker 对照可度量引入并行运行时的成本。W1-H 每会话配额 M=32，W3 的 M=1,024 且有四个市场，实际 FCN 行数仍受可访问市场、空结果和补批影响。两者的配置 M 不能直接代替每批 FCN 行数。E01 另在同一 W0 原版恢复条件上保留线程和 spawn 进程；R4A 的真实程序先导记录已经观察到进程启动与复制成本。

生产代码在 Python 端维持智能体顺序与 RNG 抽样，原生绑定在进入 evaluator 时释放 GIL，并在返回前等候任务完成。Taskflow executor 生命周期跨多个批次，任务按连续索引区间写互斥结果槽，随后 Python 按原顺序回建、提交与撮合。W3 seed 101 的 x86 V01 给出 Python 基线 `5d586ed82d0d4977a083ebfc71ff9a22`、direct `640b5f6c9bba4f7aa15d364d08e7e394` 及并行 1/2/4 workers 回执 `de8bffca9d094f57a408de772e5a245b`、`2634ac654d9f4985881fe920cd137027`、`43e87f1199734fe7bc60b680a37988bd`。它们均匹配同一独立参考 `07e25c0ca8ff4ed495db1e8f2d9639b5`。

历史低开销 pilot 保留负收益。P11 的 W2-H 同 incremental 条件，seed 11 下 Python 与 direct 分别为 0.213 和 0.272 s，seed 29 下为 0.206 和 0.240 s。R4B 的 x86 replay 则在 2,048 行时四 worker 两布局均慢于同布局 direct，在 4,096 和 8,192 行时均更快。每单元只有一次 launch，方向变化可用于定位粒度问题。真实端到端的批大小分布、调度和汇合成本仍需 E05。Amdahl 的理想式 `1 / ((1−p) + p/w)` 中，`p` 需在同一 workload、同一串行基线及同一计时边界下测量可并行区段；现有绑定总时长还含校验、分配与等待，缺少足以估计该 `p` 的同条件测量。当前没有可发表的整机 Amdahl 上限。

[生产抽样及订单回建](../../src/coreorder/native_serial.py) · [绑定与 GIL](../../native/bindings/fcn_binding.cpp) · [Taskflow 执行器](../../native/runtime/executor.cpp) · [P11 低开销台账](../roles/A/evidence/P11-runs.csv) · [华硕 P01 与进程诊断](R4A.md) · [V01 索引](evidence/R4B/v01-index.json)

### RQ3　真实 FCN 的多字段访存与转换成本

生产 AoS 从连续 struct 取一行，SoA 从 15 个列视图组合出一行，随后执行同一 FCN 公式。实际表达式使用多个价格、权重、噪声及边际字段，并执行对数和指数。SoA 的单字段连续性与 FCN 的逐行多字段访问、数值密度、绑定校验和布局写入共同决定净成本。生产缓冲区的容量按需扩展，活跃字节与预留字节由不同指标记录。正式端到端 E03 需要分别核对布局、有效 FCN 行数、保留容量、reallocation 和 packing。

R4B 将 W2-H seed 11 的原始生产行前缀用于 12 次 x86 校准。同一前缀全部四条件的输出摘要相同。每点一次启动、3,000 次绑定调用，输入加单份输出的名义存储量为 256、512、1,024 KiB。direct AoS/SoA 分别为 30.08/32.17、31.56/32.84、32.62/33.60 ns/行；四 worker 分别为 40.06/42.32、27.45/28.46、20.04/22.19 ns/行。该绑定区间含结果分配、绑定与任务等待，输入拆列在计时前。三个前缀达到报告的来宾 L2 容量量级，实际驻留和 Cache 边界受多份数组、输出、代码与线程影响。每个点共有同一真实捕获的重复使用，数据支持报告校准中的方向，无法识别容量拐点或缓存因果。V01 的 W2-H seed 101 direct AoS/SoA 回执为 `6d10cadf6ca44b87b8e40221f4e24bea` 和 `9dd51cbeb0ed47a7a1a58c4bf04f8446`，4-worker AoS/SoA 为 `a172bdfc58f3408db6a20f8adbdd0625` 和 `19cbce45be344a11a24d0c8d5dc86e80`。

R4A 已在生产 pilot 单独验证用户态 cycles/instructions、branches/branch-misses、AMD L1D 事件的采集，测试报告覆盖 100%，范围含 Python worker 与继承任务的导入、仿真及摘要。L1D 的两个映射分别是数据 Cache 访问和由 L1D miss 触发的 L2 访问。专门 LLC 事件返回 ENOENT，正式 LLC 保持缺测。现有探针和同输入 replay 尚不足以计算正式 IPC、miss rate 的组间差异。R5B 复核的 replay 源为校准 seed 11，候选 E05 则登记了 seed 101 的独立验证输入。

[同一 FCN 数值式与访存](../../native/fcn/evaluate.cpp) · [生产打包与缓冲区](../../src/coreorder/packing.py) · [replay 校准图](evidence/R5B/artifacts/pilot/replay-calibration.pdf) · [校准原始索引](evidence/R5B/replay-raw-index.json) · [实际 PMU 定义与权限](R4A.md#pmu-能力与-cache-机制证据) · [E05 候选捕获回执](../../configs/experiments/r4b/replay-source/capture-receipt.json)

### RQ4　堆恢复优化后，决策路径在 pilot 相对突出

P11 的 Apple M5 W1-H seed 11 阶段实测三条运行。原版、incremental Python、incremental direct 的 1,211 次恢复包含式时间分别为 11.498、0.294、0.276 s；120 次智能体选择和决策分别为 0.954、0.985、1.038 s。同一 direct 运行的 120 次子区段累计为随机准备 0.043 s、packing 和租约 0.249 s、原生绑定 0.00091 s、订单回建和释放 0.038 s。恢复在原版可见区段中突出，恢复缩小后智能体决策的累计时间更显著。direct 的 packing 时间在其已观测子区段中突出。定量对照限于该 pilot 的记录边界、工作负载和 seed。

完整仿真包含撮合与账本。当前的 `handle_orders_s` 可以包含 `optional_restore_s`，`draw_pack_s` 合并抽样与 packing，`native_compute_s` 包括绑定和任务汇合。cProfile cumulative 包含被调函数，不能叠加成系统用时。图按范围绘制累计秒，子区段另用坐标轴。正式 x86 上游与优化后各路径的成本占比及纯调度、同步和撮合的独立测量均待 E05。

[阶段图](evidence/R5B/artifacts/pilot/instrumented-spans.pdf) · [P11 阶段数据](evidence/R5B/artifacts/pilot/instrumented-spans.csv) · [三个 raw 文件摘要](evidence/R5B/p11-phase-raw-index.json) · [当前计时边界](../CONTRACT.md#运行模式与计时边界)

## 3. A–E 个人研究证据

| 成员 | 可引用结果与定位 | 正式性能覆盖 |
| --- | --- | --- |
| A | 原版与增量恢复的整合及堆诊断。x86 W1-H seed 101 的两恢复回执为 `4d4084b6033b4b5eb8ca82c3742dd275`、`19fe7d05557c4fe0be3b162500a9c2d8`。P11 的计数与阶段范围分别见 RQ1、RQ4。 | H01 和正式热点迁移 NOT_RUN |
| B | 同一 FCN 数值式、strict FP、pybind11 绑定和 direct 路径。W2-H seed 101 direct AoS 回执 `6d10cadf6ca44b87b8e40221f4e24bea`。 | 原生化收益 NOT_RUN |
| C | Taskflow 的持久线程池、独占结果槽、汇合和 worker 确定性。W3 seed 101 的 1/2/4 worker 回执见 RQ2。 | 扩展率、效率和调度收益 NOT_RUN |
| D | AoS/SoA 同式等价、生产 packing 及缓冲区。W2-H seed 101 的四条布局回执及校准原始索引见 RQ3。 | 布局、转换和访存正式效应 NOT_RUN |
| E | 独立 PAMS 参考、轨迹差分和回执链。W3 seed 101 独立参考 `07e25c0ca8ff4ed495db1e8f2d9639b5`，V01 总计 20 条独立参考与 125 条候选。 | 正式 timing 记录审计和配对估计待采集 |

[成员来源和工程验收](evidence/R3/README.md) · [回执索引](evidence/R4B/v01-index.json) · [x86 构建命令](evidence/R4B/compile_commands.json)

## 4. 图表、适用范围与阶段状态

| 论文用途 | 可引用产物 |
| --- | --- |
| 正确性验收 | [目标 x86 完整正确性表](evidence/R5B/artifacts/validation/correctness.pdf) |
| 堆恢复机制与工作量 | [P11/P13 pilot 机制图](../roles/A/evidence/P13/figures/heap-mechanism-pilot.pdf) |
| H01 正式端到端、E01/E02 原生化与扩展、并行效率、E03 布局 | NOT_RUN。[19 项逐比较覆盖表](evidence/R5B/artifacts/formal-pairing-coverage.csv) |
| Packing 和原生核成本、瓶颈迁移 | [P11 包含式阶段与 direct 子区段](evidence/R5B/artifacts/pilot/instrumented-spans.pdf)。正式 x86 E05 profile 缺测。 |
| 工作集及 Cache/PMU | [R4B x86 真实输入 replay 校准图](evidence/R5B/artifacts/pilot/replay-calibration.pdf)及 [R4A PMU 探针](R4A.md#pmu-能力与-cache-机制证据)。正式 PMU 缺测。 |
| 硬件及实验配置 | [目标主机与保留负载表](evidence/R5B/artifacts/validation/configuration.pdf) |

研究范围是本候选的无费市场、已验证的智能体类型、工作负载和 seed。Windows 报告 8 核 16 线程及两类效率等级；WSL2 affinity 只能约束来宾 CPU，物理异构核心归属与频率稳定性仍有限。ARM 和 x86 的资料各自使用同机对照。原版 PAMS 到最终组合的总加速缺少同一工作负载下合格的端到端测量。局部对照值不能跨工作负载合成为总加速。

R5B 数据审计、图表生成和正确性证据复核为 **PASS**。正式数据准入为 **BLOCKED**，H01/E01/E02/E03/E05 为 **NOT_RUN**。正式分析的输入为生效的同版本 G3 锁、与之匹配的封存 V01、目标 x86 的 timing/E05 批次和运行异常记录。当前可提交的研究结论止于目标机语义保持、已观测的堆比较工作量与有明确测量边界的 pilot 现象。

[图表复算及数据出处](evidence/R5B/README.md) · [G3 判定](G3.md)
