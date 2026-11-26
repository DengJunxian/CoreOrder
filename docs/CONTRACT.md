# CoreOrder 公共工程契约 R4-v1

本实现对应材料的 `coreorder-r4-v1`。源码 HEAD、三个 gitlink 和 [UPSTREAM.lock.json](../UPSTREAM.lock.json) 一起标识基线。B/D、C、E 的确认见 [G0 候选检查表](roles/A/G0_CANDIDATE.md)。

## FCN 数值 ABI

C++17 消费者链接 CMake 接口目标 `coreorder_contracts` 并包含 [contracts.hpp](../include/coreorder/contracts.hpp)。Python 消费者导入 [INPUT_DTYPE、OUTPUT_DTYPE](../src/coreorder/contracts.py)。两个记录均为本机字节序、8 字节记录对齐，C++ 头对每个 offset、`sizeof`、`alignof` 做静态断言。

| 输入字段顺序 | 类型 | 字节偏移 |
| --- | --- | --- |
| `p_now, p_fund, p_then` | IEEE float64 | 0, 8, 16 |
| `w_f, w_c, w_n` | IEEE float64 | 24, 32, 40 |
| `noise_scale, order_margin, z_noise, z_margin` | IEEE float64 | 48, 56, 64, 72 |
| `window, effective_window, mean_reversion` | int64 | 80, 88, 96 |
| `margin_type, chart_sign` | int32 | 104, 108 |

输入记录 112 字节。`margin_type` 取 fixed=0、normal=1。`chart_sign` 取 +1 或 −1。`effective_window=min(market_time,window)`，`p_then` 读取该窗口端点。fixed 的 `z_margin` 取 +0.0，原 Python 随机流不额外抽样。输出记录 16 字节，`price:float64@0`、`side:int32@8`、`error:int32@12`。side 的 −1、0、+1 对应卖、无单、买，成功无单的 price 为 +0.0。逐行 metadata `agent_id, market_id, call_index` 独立于两种数值布局。回填按原行序与代理组恢复 PAMS 订单。

| 行错误 | 整数值 | 上报条件 |
| --- | --- | --- |
| `ok` | 0 | 行求值成功 |
| `invalid_input` | 1 | 输入超出支持域 |
| `unknown_margin` | 2 | margin 枚举无定义 |
| `nonfinite` | 3 | 输入或数值结果非有限 |

## 视图、range 与错误

- `InputView` 选择 `AosInputView` 或由相同 15 个只读标量列组成的 `SoaInputView`。`OutputView` 借出 `n` 个可写 `OutputRow`。布局、shape、dtype、本机端序、C 连续性、NumPy `ALIGNED` 与实际地址模数均在 B 的边界检查。AoS 与输出地址分别满足对应记录对齐，SoA 每列满足对应标量对齐。零长度允许空指针且不解引用。运行到完成前，持有输入和输出 owner，缓冲区不重分配。
- B 在 `evaluate_range(input, output, begin, end)` 使用同一 scalar 公式。`RowRange::valid_for(n)` 定义闭开区间 `0 ≤ begin ≤ end ≤ n`。C 的持久执行器按选定策略覆盖 `[0,n)` 恰好一次，允许空范围，每次只写任务的独占输出槽。C 向 A/B 提交 `run_ranges` 的生产签名和异常证据，worker 不持有 Python 对象。
- 视图或参数非法，在发任务前明确报错。行数值失败写本行错误码。执行器异常等待任务终止并传播，恢复 GIL 后检查按行索引最早的失败。失败批次整体不回填，保留故障上下文并终止 run。禁止消耗 RNG 后以另一个后端重试。正式严格构建保持表达式顺序、禁 fast-math 和 FMA 收缩，位级承诺以同环境差分为准。

## 运行配置与证据

[workload](../schemas/workload.schema.json) 是 PAMS JSON，保留原字段和业务参数。[run_config](../schemas/run_config.schema.json) 独立声明 backend、book_restore、layout、workers、grain、schedule 和 seed。Python 后端的 layout 为 `not_applicable`，py-seq 和 native-serial 均用一个 worker，native-serial 不建 executor。统一入口支持五种后端和两种堆恢复，两种原生后端均支持 AoS 与 SoA。原生并行默认 grain=128、schedule=static。进程后端固定 spawn，复制诊断读取实际 dispatch 任务。增量路径的有效配置只替换所用市场组的类名。无法执行的组合与类型显式退出，并记录请求与是否进入对应运行路径。 [恢复方法和诊断](roles/A/HEAP_METHOD.md) · [P09 能力表与证据](roles/A/INTEGRATION.md)

[records.schema.json](../schemas/records.schema.json) 的 `$defs` 提供 `manifest`、`metrics`、`status`、`environment`、`event`、`market_frame`、`step_state`、`final_state`、`final_rng` 和 `fcn_row`。可用 `coreorder.schema.validate_record(kind, parsed_json)` 检查相应记录。manifest 记录原始和有效配置 hash、源码和上游 SHA、模式及工作量。单次运行的四个配对字段为 null 并附原因。metrics 对未测值用 null，并在 `unmeasured` 和 `missing_reasons` 保留原因。`metric_sources` 标记实测或派生值。环境记录实际导入路径、依赖、机器、工具链和实际加载的扩展。

- `events.jsonl` 按 PAMS 入队的产生顺序保存 `event_seq`、session、step、种类、市场、代理及订单 ID、适用的 side、TTL、成交量和价格。成交包含买卖双方、原订单 ID 和费用。session 使用事件产生时的当前 session。比较时排除身份字段 `run_id`，保留行的产生顺序。
- `market_steps.jsonl` 保留每市场自己的 `MarketStepEndLog` 观察。`step_states.jsonl` 每全局 step 在首个 `MarketStepEndLog` 拍一帧，该点位于订单处理后和首个市场 after-step hook 前。帧中有逐代理现金、持仓、普通 FCN 参数、各市场状态及逻辑订单簿和 RNG 摘要。
- 最终状态在原 runner 返回后记录账户、各市场最终簿和完整市场、基本面、成交量历史。旧诊断的 `final_state.json` 同时带初始账户，显式 `validation` 的独立轨迹保留初始快照。只用上游比较器规范逻辑簿，事件与回填行保持原序。最终 RNG 包含 runner、simulator、agent、market、session、事件及 fundamentals 的 Python 状态和 gauss 缓存，以及 fundamentals 的 NumPy bit-generator state。浮点使用可逆 hex。

## 运行模式与计时边界

在相同业务配置下，`coreorder run --mode` 的四种模式共用 PAMS 市场及调度入口、同一数值核和对应后端的执行器。manifest 记录实际 runner 类、Python 并行执行器类（适用时）、进程启动方法及原生布局绑定。未指定 `--mode` 时兼容旧诊断命令与产物。

| 模式 | 观测及回执 |
| --- | --- |
| `validation` | 保存完整交易事件、逐步状态和 RNG，用 E 的独立固定 PAMS 进程执行结构差分，保留两份轨迹、比较和首处分歧包。该单次结构差分独立于正式 V01 准入。 |
| `timing` | 在 PAMS 原有日志处理点按对象类型批量计数，涵盖实际订单、撤单、过期、成交和市场步。原生同时保留总 agent calls、decision rows 和 Gaussian API 调用计数。关闭逐步快照、事件 JSON、比较器探针、函数剖析、进程复制探针和原生批次宽度历史。 |
| `profile` | 沿用轻量业务路径，在控制线程测阶段与选定函数的包含式时长。`--cprofile` 切换到独立的函数剖析运行，输出 `profile.prof`，阶段字段缺测。剖析样本用于诊断。 |
| `pmu` | 使用 `--pmu-event EVENT` 指定目标 Linux 上已确认的事件，可重复指定。外部 `perf stat` 计数覆盖 Python 子进程生命周期及继承的任务。保留 `perf-stat.csv` 与 `pmu.json`、原始计数、事件名和运行比例。PMU 缺失返回 `UNSUPPORTED`，perf 或事件采集失败保留原始错误与退出码。 |

| 字段 | 测量范围 |
| --- | --- |
| `setup_s` | runner 构造、读取有效配置、PAMS 初始化和执行器构造。Taskflow 的线程在构造时启动。环境核验、原始配置和有效配置归档在此计时之前。 |
| `simulation_s` | 从进入 PAMS 仿真到执行器完成 shutdown。包括选择智能体、随机数准备、packing、原生调用、提交和等待、订单重建、撮合、账户更新及 PAMS 日志处理。Python 线程与 spawn 进程在首次提交时按需启动，实际启动开销计入仿真。原生与 Python 并行均在结束处完成 join。最终状态、逻辑簿排序、完整 RNG 摘要和结果写盘在计时后。 |
| `process_wall_s` | 父进程从启动 Python 子进程到完成等待和输出回收，含解释器启动、初始化、仿真、摘要与写盘。validation 还包含其独立比较。PMU 模式父进程测到的是 perf 与 Python 的联合生命周期，只记录在 `launch/command.json`。 |
| `draw_pack_s` | 从进入原生批处理到调用布局绑定，含抽样准备和打包。外层智能体抽取计入 `simulation_s`。 |
| `native_compute_s` | 原生布局绑定调用及返回之间的整段，含绑定验证、结果缓冲区、数值核和任务等待。 |
| `rebuild_orders_s` | 从原生布局绑定返回到退出批处理，含订单重建及缓冲区释放。 |
| `handle_orders_s` | PAMS `_handle_orders` 的包含式时长，覆盖其订单处理、撮合及账户更新。 |
| `optional_restore_s` | 两种 `_execution` 中用于恢复的实际 `heapify` 或 `heappush` 调用，含内部比较。它可能包含在 `handle_orders_s` 内。 |

后五个字段由默认 profile 模式采集，原生专属阶段在 Python 后端为空。阶段有嵌套，结果用于定位成本。正式系统耗时使用 `timing` 的 `simulation_s`，正式实验仍须通过 [G3](gates/G3.md)。P11 pilot 和旧诊断的时长保留原口径。 [Linux perf stat 手册](https://github.com/torvalds/linux/blob/master/tools/perf/Documentation/perf-stat.txt)

## R3 回执身份与现行研究范围

`input_hash` 绑定原始 workload 字节，`effective_config_hash` 绑定 runner 实际读取的有效字节。`canonical_input_hash` 绑定解析后的工作负载，使用排序键、紧凑分隔符、ASCII 转义、无尾换行的 JSON UTF-8 字节计算 SHA-256。E 用规范化身份比较原版和生产轨迹，原始字节与有效字节由生产记录和证据封存核验。

R3 研究验收涵盖无费普通市场、精确 FCNAgent 和已测上游 MarketMakerAgent。生产入口支持运行前选择 `py-seq`。组长已批准将正式研究限定于无费市场。原生接口显式拒绝不支持的类型，用户可在运行前选择 `py-seq`。自动整 run fallback 不属于本轮验收范围。 [R3 验收](gates/evidence/R3/README.md) · [组长范围决定](gates/evidence/R4B/leader-decisions.json)

## 独立验证入口

`python -m coreorder validate --suite smoke|g0 --output <new-directory>` 会调用 E 所有的 `validation/e1.py`。协议和返回条件见 [E 交接](roles/A/P03_HANDOFF_E.md)。A 的共享观察器和 fixtures 可作接口参考，E 仍需独立采集原版轨迹并比较。缺方法时 CLI 记录 BLOCKED 并退出 3。
