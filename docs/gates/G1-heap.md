# G1-heap 增量堆恢复验收

## R3 当前候选验收 · 2026-11-26

**本机技术 PASS，正式 G1-heap BLOCKED。** 在 `88fee6f1dafeeabc44750913fa2e59d518a3e1e5` 重跑 P06 的 23 对完整仿真和 8 个定向边界。独立成员 E 工具另完成 38 对真实对照。交易顺序、后续出堆、逻辑簿、账本、历史及 RNG 相同。生产撮合、账户更新及事件入口继续由原 PAMS 提供。待同版本 G0 和 E 签认。 [R3 证据](evidence/R3/README.md)

## P06 历史记录

**2026-11-25（上海时间） · P06 本地独立验收 PASS · 正式 G1-heap BLOCKED**

受测生产源码为 P05 `2db0c2b9bed127b72119b83c6bf23293d5e5ee58`，契约 `coreorder-r4-v1`。参考为 EPL-1.0 的 PAMS `6cd53810103780770c5b5d6ee0069ccab9f4b358`，从干净 vendor 直接调用原 `SequentialRunner.main()` 和原 `Market`。生产增量路径通过 `run_py_seq` 驱动实际 `CoreOrderMarket`。两套审计的 checkout 分别为组长 `1306f2addf1e59d825bf4ca0b55c27f98ec1c054` 与 E 工具复跑 `457094ea5ca14068cfa723053243a5056a74ff7f`，生产源码、依赖锁及三个 gitlink 均与 P05 一致。本机为 macOS 27.0 ARM64、CPython 3.12.13，`pip check` 通过。 [运行日志](evidence/P06.txt)

## 验收矩阵

| 检查 | 状态 | 实测证据 |
| --- | --- | --- |
| 固定源码与最小 diff | **PASS** | 原版模式保留原 `Market`。增量在待成交收集和原成交执行之间，将拼接与整体建堆替换为两侧逐项压回。核对方法继承、许可与上游工作树。 |
| 包内完整模拟 | **PASS** | 8/8 对。fixed/normal × 窗口及 TTL 档 [3, 6]/[100, 200] × seed 42/20261125。每场景 64 个代理、60 步、每步配额 16。 |
| C01 代表配置 | **PASS** | 15/15 对。使用 E 交付的原始配置字节 `C01a-M1`、`C01b-normal`、`C01g-fundamental-shock`，各跑 101/202/303/404/505。normal 场景各有 6–8 笔成交，冲击场景各有 10–11 笔过期、零成交。 |
| 定向边界 | **PASS** | 包内 7/7，另复验连续新单。覆盖部分成交、多价位、同价同时间不同 ID、市价对限价、两侧市价量相等但限价不交叉、无可定价、撤单、过期和全限价不交叉。 |
| 逐条语义与首差 | **PASS** | 逐条比较按产生顺序写入的下单、成交、撤单和过期，在逐步及逐操作帧比较逻辑簿、实际后续出堆顺序、TTL 索引、账户及 RNG 摘要，另逐字节比较完整历史和最终 RNG。生产对照没有首差。对真实轨迹副本注入首个订单 ID 的变动，返回第 0 行 `order_id`，含邻近记录、配置、种子和两侧完整 RNG 路径。 |
| 双侧诊断与调用点 | **PASS** | 独立调用计数核对合法余堆、原对象身份及逐行 `n=h+k`，与两条生产 CLI 的诊断 JSON 完全一致。增量恢复 `heapify=0`；独立核验两条路径保有正常建簿、非堆顶移除和到期清理调用。 |
| E 工具同版本复跑与交叉核对 | **PASS** | 原样使用 E `b05d5555fa5cc756a91ab61c644e797ca227c26f` 的独立参考、比较器和不变量检查。38/38 对通过，各案的配置身份、结构判定、守恒、事件和检查点计数与已有独立结果一致。两套当前采集器在共同的 23 对上逐条核对原始配置、有序金融事件及字段。 |
| 回归与上游入口 | **PASS** | 项目 pytest 80/80。`validate --suite smoke` 与 `--suite g0` 以 0 退出，使用 P05 保留的原版路径。 |
| 正式 G1-heap | **BLOCKED** | G0 共同基线尚未正式签认。PR #1 仍为 Draft，`main` 指向初始化提交。E 的工具和同版复跑结果已具备，成员 E 对当前共同候选的审阅回执尚未取得。 |
| 正式性能及硬件计数 | **NOT_RUN** | 本轮采集恢复机制与语义证据。 |

E 的采集器覆盖原版日志、市场推进后逐步状态、按原比较器规范化的逻辑簿和完整 RNG。候选直接使用 P05 观察钩子，逐帧只移除增量市场的 `book_restore` 运行元数据。组长采集器另从簿副本反复 `heappop`，核对实际后续出堆序列。两套采集器的逐步观察时点各按原约定，交叉核对共同的金融日志和字段。 [E 的 G1 交付说明](G1-E.md) · [G0 当前状态](G0.md) · [PR #1](https://github.com/DengJunxian/CoreOrder/pull/1)

## 源码差异与等价前提

| 调用段 | 逐行审查结果 |
| --- | --- |
| 可执行性与收集 | 原 `remain_executable_orders` 和 `_collect_pending_executions` 保留。`price is None` 断言仍在恢复前。扫描按上游 `_get_execution_price` 计算统一价，成交余量在局部变量中递减。 |
| 暂取订单恢复 | 原版将暂取与剩余引用拼接后两次整体 `heapify`。增量向两个仍为合法堆的原队列逐项压回同一对象。 |
| 提交成交 | 按原 pending 列表顺序将同一统一价、配对和量交给 `_execute_orders`，保留末尾可执行性检查。原比较器、`OrderBook`、`SequentialRunner` 和 `Simulator` 继续负责优先级、撤单、过期、费用、资金与证券。 |

扫描只从堆顶 `heappop`，所以余堆合法。正常入簿分配市场内唯一的订单 ID，扫描期间比较字段保持固定。对同一侧已入簿的市价单和有限价订单，上游比较器按市价优先、限价方向、挂单时间与订单 ID 形成唯一优先序。恢复前后核验原对象和字段，包括 TTL，合法堆的物理数组允许不同，逻辑出堆序列相同。 [方法及许可](../roles/A/HEAP_METHOD.md) · [原版撮合](../../vendor/pams/pams/market.py#L1083) · [原版比较器](../../vendor/pams/pams/order.py#L194)

每侧以 `n` 表示暂取前长度、`k` 表示暂取数、`h` 表示余堆长，满足 `n=h+k`。拼接及整体建堆为 `O(n)`。增量做 `k` 次堆上滤，调整工作量为 `O(k log max(n, 2))`，列表追加按摊销计。`k=0` 时恢复无压入。小堆与较大恢复比例下的实测运行时间留给正式实验。

## 恢复诊断

CI2002 smoke，seed 42，两种模式各 **12 次恢复**。下表按侧汇总，比例由每次的 `k/max(n,1)` 计算。p50 为中位数，p90 为最近秩。

| 侧 | Σn | Σk | Σh | 比例 min / p50 / p90 / max | 恢复比较数，原版 → 增量 |
| --- | ---: | ---: | ---: | --- | ---: |
| 买 | 268 | 26 | 242 | 0.0690 / 0.0851 / 0.2000 / 0.3077 | 433 → 97 |
| 卖 | 233 | 26 | 207 | 0.0870 / 0.0909 / 0.1818 / 0.5000 | 377 → 93 |

原版两侧合计 `heapify=24`、`heappush=0`，增量为 `heapify=0`、`heappush=52`。撤单及过期定向用例中，两条路径各执行 2 次建簿、1 次非堆顶移除和 1 次到期清理的 `heapify`。诊断运行中的独立计数按实际直接调用点归属恢复操作。尺寸诊断与比较计数的独立开关已通过项目回归。本表记录操作工作量。

## 复现与停止条件

~~~sh
.venv/bin/python -B tests/heap/audit_p06.py --output results/acceptance/g1-heap/p06-leader-rerun
.venv/bin/python -B tests/heap/audit_p06_member_e.py --output results/acceptance/g1-heap/p06-e-rerun
.venv/bin/python -B -m pytest -q -p no:cacheprovider
~~~

原始证据位于 `results/acceptance/g1-heap/p06/`。`leader-verified/` 保存逐案 workload、边界操作、两侧时间线、完整 RNG、方法 diff、独立诊断和负对照。`member-e/` 保存 E 的归档源码、身份、逐案压缩轨迹和结构判定，`crosscheck.log` 保存与历史结果及两套当前采集器的核对。首轮审计发现外层 `kind` 与 PAMS 订单 `kind` 重名，导致负对照定位不到日志类型。改用 `record_type` 后重跑通过。原失败与复跑同时保留，生产语义修复 **0/2**。 [组长审计](../../tests/heap/audit_p06.py) · [E 工具复跑](../../tests/heap/audit_p06_member_e.py) · [原始日志摘录](evidence/P06.txt)

正式签认等待共同 G0 SHA 和成员 E 对相应候选的审阅回执。P06 停在已完成的本地技术验收与明确阻断记录。
