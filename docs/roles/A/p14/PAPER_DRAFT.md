# PAMS 上的语义保持优化

## 引言 · 平台与研究对象

金融多智能体仿真把代理决策、订单处理和市场状态更新放在同一反馈回路中。本文研究固定版本 PAMS 上的两个执行问题。一是在每次撮合扫描后如何恢复订单堆，二是如何在保留随机流和提交顺序的条件下合批执行普通 FCN 决策。选择 PAMS 是因为它提供可核查的 Python 市场、会话、FCN 策略、双侧订单簿及 CI2002 样例，可在同一份金融实现上改变执行机制。原版串行程序也能在独立进程中运行，提供同配置、同 seed 的参考。本文固定 PAMS `6cd53810103780770c5b5d6ee0069ccab9f4b358`。平台论文用于说明设计来源，具体行为以该提交为准。 [PAMS 预印本，Hirano、Takata 与 Izumi，2023](https://arxiv.org/abs/2309.10729) · [固定平台源码与样例](https://github.com/masanorihirano/pams/tree/6cd53810103780770c5b5d6ee0069ccab9f4b358)

## 系统语义 · 原版执行

每个允许下单的市场步中，`SequentialRunner` 以自己的随机流抽样排列全部普通代理，依次调用策略。达到 `maxNormalOrders` 个返回非空列表的代理后停止采集。一次代理调用可以访问多个市场并产生多条订单。普通代理的各组订单随后由上游 `_handle_orders` 再抽样排列，按组处理真实订单与撤单，并保留原有 HFT 触发点。入簿和撤单可触发撮合。模拟器按成交日志顺序更新资金与持仓，原步前、步后事件和市场时间推进继续由 PAMS 执行。研究对象是该顺序约束下的受支持普通市场及精确类型 `FCNAgent`。 [调度与订单处理源码](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/runners/sequential.py#L561-L746) · [账户更新源码](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/simulator.py#L243-L267)

## 方法 · 恢复成本

`Market._collect_pending_executions` 从买卖侧暂取最优订单，以局部剩余量推进匹配，同时记录配对引用、每对的成交量与统一价格。原版在正式执行这些成交前，为每侧新建包含暂取和剩余订单引用的列表，再执行全表 `heapify`。暂取前堆深为 `n`，暂取为 `k`，剩余为 `h=n-k`。即使 `k` 很小，拼接和建堆仍处理 `n` 个引用，单侧成本为 `O`n``。建表沿数组遍历引用，建堆比较还要访问 Python 订单对象。这里可从源码识别调用和数据访问范围，硬件缓存命中与内存流量需单独测量。 [固定匹配与恢复源码](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/market.py#L1083-L1199)

## 方法 · 增量恢复与正确性

`CoreOrderMarket` 在同一位置把暂取的原对象逐项 `heappush` 回两侧余堆。该步骤依赖四个条件。扫描期间只从各侧弹出根，余堆仍合法。恢复对象及其比较字段保持不变。已入簿的合法订单在同一侧由类型、限价方向、挂单时间和唯一订单 ID 确定严格优先序。恢复完整地放回原对象后，原有成交处理才能继续。两个堆的物理数组可以不同。对相同的单侧订单集合，合法堆的根都指向同一个唯一最优订单。依次出堆并对剩余集合归纳，可得相同的逻辑出堆顺序。实际成交以原 pending 列表直接执行，其统一价在恢复前即由扫描中最后一个可定价配对确定，因此逐项压回不改变价格形成、配对身份和成交量。撤单、到期和其他上游建堆入口继续使用原实现。 [增量适配源码](../../../../src/coreorder/market_adapter.py) · [优先序源码](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/order.py#L195-L239) · [等价前提、许可和差分](../HEAP_METHOD.md)

单侧做 `k` 次堆上滤，堆调整最坏工作量为 `O(k log(n+1))`。列表追加的成本按摊销计，单次批恢复仍可能遇到容器扩容。少量根弹出和深簿为减少调整提供条件。较浅订单簿或高恢复比例时，线性建堆和逐项压回的实际代价受分支、对象比较与分配行为影响，不能仅凭复杂度判断胜负。报告按买卖侧保留 `n,h,k`、`k/max(n,1)` 和恢复比较次数。 [机制示意](figures/heap-restore.pdf) · [G1-heap 定向边界与诊断](../../../gates/G1-heap.md)

## 方法 · 安全批次及原随机流

普通代理仍由上游规则做一次全排列。设尚余 `r` 个非空代理名额，从排列前缀取至多 `r` 个候选。每个候选最多消耗一个名额，所以在当前批次内无论哪些代理返回空列表，都不会提前跨过原串行的停止点。批次消费后根据实际非空数补批。采集期普通 FCN 读取当步市场信息，主线程按原代理与可访问市场次序调用各代理的 `Random.gauss`。每条所访问市场行消耗一次噪声采样，normal margin 还消耗一次边际采样，包括之后可能没有订单的路径。该 API 的缓存也是 RNG 状态的一部分，跳过一次调用会影响当前或后续输入。 [批次实现](../../../../src/coreorder/native_serial.py#L79-L128) · [原 FCN 分支](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/agents/fcn_agent.py#L122-L252) · [CPython 3.12 Random 源码](https://github.com/python/cpython/blob/v3.12.11/Lib/random.py)

D 按实时状态和原始随机样本打包 AoS 或 SoA。B 的同一 FCN 数值核用 direct loop 串行计算，或由 C 的持久 Taskflow 执行器分块调度。worker 在独占槽写数值结果，汇合后主线程按元数据中的调用编号和市场序重建真实 `Order`。原 runner 继续完成原有二次抽样、订单检查、提交、HFT、撮合和账本更新。若进入批次时状态和 RNG 一致，且每行输出精确一致，则本批次的订单列表及其顺序一致。原有提交规则因此得到同一输入，可逐批、逐步归纳。该推理限定在无此类额外副作用的精确 FCNAgent 和受支持市场。事件因果约束的背景可参见 Chandy 与 Misra，以及 Fujimoto 的 PDES 综述。 [执行数据流](figures/execution-dataflow.pdf) · [模块集成与边界](../INTEGRATION.md) · [Chandy 与 Misra，1979](https://www.cs.utexas.edu/~misra/scannedPdf.dir/DistrSimulation.pdf) · [Fujimoto，1990](https://doi.org/10.1145/84537.84545)

## 验证与实验设置

参考程序从独立加载的固定 PAMS 运行 `SequentialRunner`。E 的观察器保留发生顺序，对事件、每步状态、逻辑订单簿、账户、市场历史和完整 RNG 作结构差分，并保存首个差异与可重放输入。浮点值用可逆十六进制表示，逻辑簿用原比较器确定顺序。P06 在固定 PAMS 上通过 23 对完整仿真和 8 个定向用例的本地 heap 技术核验。P10 的 56 个真实组合在语义对照中一致，不过 E gate 在 `input_hash` 配置身份字段拒绝回执，E records 还拒绝 `setup_s` 的来源记录，正式 G2 仍待共同签认。 [E 的参考入口](../../../../validation/reference.py) · [结构差分](../../../../validation/compare.py) · [G1-heap 原始记录](../../../gates/G1-heap.md) · [G2 原始记录](../../../gates/G2.md)

H01 候选在 W0-H、W1-H、W2-H 上固定 `py-seq` 与同一负载，仅切换恢复方式。每个工作负载计划使用 seed 101、202、303、404、505，每 seed 三个预定的配对区组，预热独立执行。计时包括完整仿真中的随机准备、策略求值、交易和账本更新，初始化与摘要另计。比较器计数、剖析及硬件指标分别采集。统计程序先计算区组内对数耗时比，按 seed 取三个重复的中位数，再求五个 seed 效应的几何平均并按 seed 做 bootstrap。正式计时须有全部拟测配置和 seed 的 V01 语义回执。分辨不确定性层级的依据见 Kalibera 与 Jones，具体种子和统计参数来自 R4 候选协议。 [G3 候选与状态](../../../gates/G3.md) · [Kalibera 与 Jones，2013](https://kar.kent.ac.uk/33611/)

## 结果 · 堆恢复与瓶颈迁移

**正式 H01 与 E05 尚未运行。** G3 未生效，V01 的合格回执为 0/140，目标 x86 主机没有构建或环境回执。因此正式端到端收益、负效应、区间、瓶颈迁移和 PMU 结果均留空。下述结果来自 Apple M5 的 P11 本机 pilot，使用 seed 11 和 29。 [正式状态表](../evidence/P13/formal-status.json) · [raw 索引与复算](../evidence/P13/INDEX.md)

三种负载的六个 pilot 配对具有相同的有序金融事件、终态与 RNG。W1-H、seed 11 的买卖侧堆深中位数分别为 423 和 307，暂取量中位数均为 2，恢复比较次数从 1,710,577 降到 38,953。W2-H、seed 11 的堆深中位数增至 925 和 812，暂取量中位数仍为 2，比较次数从 8,245,535 降到 92,206。小簿 W0 的恢复比例中位数较高，六对中最高的单条恢复比例约为 53.5%。这些数据说明在受测深簿、低暂取量的配置中，优化减少了恢复比较工作。各点同时随负载配置变化，现有设计无法单独识别恢复比例对总用时的因果效应。 [堆机制图](../evidence/P13/figures/heap-mechanism-pilot.pdf) · [图表数据](../evidence/P13/figures/heap-mechanism-pilot.csv)

W1-H、seed 11 的原版 cProfile 中，heapify 累积 2.499 秒，同次剖析总时间为 2.903 秒。增量后 `Random.sample` 累积 0.151 秒，约占同次剖析总时间 32%。独立分段探针观察到专属恢复段 11.498 秒与 0.294 秒。这两套观测各有仪器化和作用域。相同增量堆路径下，W2-H 和 W3-START 的 native-serial 在低开销 pilot 中未进一步降时，W4-START 两个种子的结果方向不一。W1-H 原生串行的分段观察显示 packing 与订单回建仍消耗时间。这些结果支持后续测量串行残余成本。 [P11 逐次运行](../evidence/P11-runs.csv) · [分段和调用次数](../evidence/P11-phases.csv) · [P11 环境与结果](../RESULTS.md)

## 讨论 · 分离机制、适用边界和有效性

堆优化改变恢复算法的工作量。Python/C++ 原生化改变策略求值执行方式，并引入随机准备、打包、绑定和回建代价。多核分块改变同一数值核的执行并发，产生调度和汇合代价。布局与缓存假设需要在同公式、同负载及同线程配置下比较可解释的硬件事件；恢复比较次数无法估计 Cache miss。若可并行部分占基线时间的比例为 `f`，忽略额外代价时 `p` 个 worker 的理想上界为 `1 / ((1-f) + f/p)`。因此采样、随机准备、订单提交和市场更新即使在核很快时仍可限制整体收益。 [Amdahl，1967](https://www.cs.cmu.edu/~18742/papers/Amdahl1967.pdf) · [pilot 成本边界](../RESULTS.md)

结论限定在固定 PAMS 版本、有限的 FCN 配置和本机 pilot。Apple M5 的异构核与热状态、Python 与 libm 版本、浮点表达式的编译行为、实际簿深分布和代理配额均可影响外部有效性。P11 将低开销运行、计数与剖析分别记录，保留两次 instrumented timeout 及复跑。物理第二设备、正式 V01 和硬件事件尚缺，暂不比较跨设备速度或缓存收益。 [边界和失败台账](../evidence/P13/INDEX.md) · [G3 应用条件](../../../gates/G3.md)

## 贡献归属

PAMS 提供市场模型、FCN 策略、事件、优先序、统一价撮合和账本，项目保留相应来源及 EPL-1.0。二叉堆操作、保序归纳和成熟运行时技术均有既有来源。A 的新增工作是锁定并接入上游、识别暂取后的合法余堆条件、实现最小恢复替换与诊断、设计批次配额适配与顺序回建，并完成平台级复验及机制分析。B 的数值核和 binding、C 的持久 Taskflow 执行器、D 的 live packing/布局以及 E 的独立验证由各成员分别提供。公开发布候选应保留固定来源、衍生许可、失败记录及可重算数据。 [上游清单](../../../../UPSTREAM.lock.json) · [第三方说明](../../../../THIRD_PARTY_NOTICES.md) · [团队所有权](../../../TEAM.md)
