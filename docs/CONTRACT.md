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

[workload](../schemas/workload.schema.json) 是 PAMS JSON，保留原字段和业务参数。[run_config](../schemas/run_config.schema.json) 独立声明 backend、book_restore、layout、workers、grain、schedule 和 seed。Python 后端的 layout 为 `not_applicable`，py-seq 和 native-serial 均用一个 worker，native-serial 不建 executor。现有可执行组合为 `py-seq/upstream`，不支持的组合退出非零并记录请求与空有效后端。

[records.schema.json](../schemas/records.schema.json) 的 `$defs` 提供 `manifest`、`metrics`、`status`、`environment`、`event`、`market_frame`、`step_state`、`final_state`、`final_rng` 和 `fcn_row`。可用 `coreorder.schema.validate_record(kind, parsed_json)` 检查相应记录。manifest 记录原始和有效配置 hash、源码和上游 SHA、模式及工作量。诊断 run 的四个配对字段为 null 并附原因。metrics 未采指标为 null 并记录原因，环境记录实际导入路径和依赖、机器及工具链，未加载 native 扩展时相应字段为空。

- `events.jsonl` 按 PAMS 入队的产生顺序保存 `event_seq`、session、step、种类、市场、代理及订单 ID、适用的 side、TTL、成交量和价格。成交包含买卖双方、原订单 ID 和费用。session 使用事件产生时的当前 session。比较时排除身份字段 `run_id`，保留行的产生顺序。
- `market_steps.jsonl` 保留每市场自己的 `MarketStepEndLog` 观察。`step_states.jsonl` 每全局 step 在首个 `MarketStepEndLog` 拍一帧，该点位于订单处理后和首个市场 after-step hook 前。帧中有逐代理现金、持仓、普通 FCN 参数、各市场状态及逻辑订单簿和 RNG 摘要。
- 最终状态在原 runner 返回后记录初末账户、各市场最终簿和完整市场、基本面、成交量历史。只用上游比较器规范逻辑簿，事件与回填行保持原序。最终 RNG 包含 runner、simulator、agent、market、session、事件及 fundamentals 的 Python 状态和 gauss 缓存，以及 fundamentals 的 NumPy bit-generator state。浮点使用可逆 hex。市场事件的效应从真实状态观察确认，同一次仿真的状态与时长字段分离。

## 独立验证入口

`python -m coreorder validate --suite smoke|g0 --output <new-directory>` 会调用 E 所有的 `validation/e1.py`。协议和返回条件见 [E 交接](roles/A/P03_HANDOFF_E.md)。A 的共享观察器和 fixtures 可作接口参考，E 仍需独立采集原版轨迹并比较。缺方法时 CLI 记录 BLOCKED 并退出 3。
