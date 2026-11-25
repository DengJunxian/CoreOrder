# 成员 A 研究记录

## P01 固定研究底座

PAMS 的 PEP 517 元数据由固定提交声明的 `uv_build` 生成。按锁构建 wheel 并记录来源，在不修改上游源码的前提下给后续独立差分保留稳定的参考入口。后续应从固定 `SequentialRunner` 和官方 CI2002 验证平台行为。

测试扩展验证了 ARM64 上 C++17、pybind11 与 Taskflow 可联用。Release 编译命令含 `-O3 -fno-fast-math -ffp-contract=off`。该记录的证据范围为构建、扩展加载与两个独立任务的结果，另见 [P01 日志](evidence/P01.txt)。

## P02 固定 PAMS 的串行业务路径

| 环节 | 固定上游入口与继承语义 |
| --- | --- |
| 初始化和基本面 | `Runner.__init__` 从输入 `Random(seed)` 派生模拟器种子。 `SequentialRunner._setup` 依上游配置生成市场、代理、session 与事件并执行 setup。 `Simulator._update_times_on_markets` 推进市场时钟，`Fundamentals` 使用自己的 Python 和 NumPy 随机状态。 |
| 普通代理激活 | `SequentialRunner._collect_orders_from_normal_agents` 抽取原代理排列，逐个调用 `submit_orders`，达到非空列表额度即停。原版 CI2002 两段 session 均继承 `Session.max_normal_orders=1`。 |
| FCN 和随机数 | `FCNAgent.submit_orders` 按市场列表遍历。`submit_orders_by_market` 先查访问权限，再读市场价格、历史和基本面。固定 margin 对可访问市场调用一次 `gauss`，正态 margin 调用两次，保留高斯缓存、原公式、报价方向、数量和 TTL。 |
| 订单提交和 HFT | `SequentialRunner._handle_orders` 用原 runner 随机流重排非空订单组，保留组内序列，处理每组后按原门控执行高频代理。 `_process_order` 沿用事件 hooks、订单确认和撤单归属检查。 |
| 订单簿和撮合 | `Market._add_order` 处理 tick 价及市场内订单 ID。 `Order._gt_lt` 实现市价优先，限价按对应买卖方向价格、时间和 ID 排序。 `OrderBook` 沿用撤单、减量及 `placed_at + ttl < time` 的过期规则。 `Market._execution` 保留原堆恢复和统一成交价，末个含限价单的匹配决定本次统一价格。 |
| 成交、账户和市场事件 | `Market._execute_orders` 更新成交与簿状态。`Simulator._update_agents_for_execution` 更新买卖双方资金、交易费和持仓，之后沿用代理回调及成交 hooks。原 before/after session 与 market step hooks 仍由 `SequentialRunner` 在原位置驱动。 |

P02 的 `py-seq` 直接调用同一个上游 `SequentialRunner` 的 `_setup`、`_run`，用单调时钟分别记录初始化和仿真。另一个入口直接调用未修改的 `SequentialRunner.main()`。共享观察器在 `Logger.write` 入队时按产生顺序记录委托、撤单、过期及成交，市场价格来自 `MarketStepEndLog`，位置在该市场 after-step hook 和时钟推进前。订单簿快照对每侧复用上游比较器排序，不调整事件顺序。

同 seed 的核验覆盖逐条交易事件、逐步市场观察、初末账户、最终逻辑簿与已记录的 RNG 状态。其中含代理、市场、session、事件、runner、simulator 和 fundamentals 的 Python 状态及 fundamentals 的 NumPy bit-generator 状态。账户仅记录初末时点，完整逐步状态与独立验证门由后续阶段落实。 [P02 命令与结果](evidence/P02.txt)
