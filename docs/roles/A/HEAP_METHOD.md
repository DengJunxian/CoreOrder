# P05 增量订单堆恢复

CoreOrder 将撮合扫描时暂取的订单逐项压回各侧剩余的堆。默认模式 `book_restore=upstream` 使用原版 PAMS `Market`，适配类选择该模式时也直接调用 `super()._execution()`。`book_restore=incremental` 在串行入口使用 `CoreOrderMarket`。原始 workload 按字节保存，有效配置只替换参与仿真的普通市场组的类名。两个配置分别记录哈希。当前增量入口支持普通 PAMS `Market`，请求 `IndexMarket` 等其他市场类时在启动仿真前返回 `UNSUPPORTED`。

## 固定源码与等价条件

1. `Market._execution` 先调用 `remain_executable_orders`。允许撮合时，`_collect_pending_executions` 按原规则弹出买卖堆顶，将原对象保存在暂取列表中，以局部变量计算每笔订单的可用余量。暂取列表可包含最终没有成交的订单，例如遇到停止交叉的第一档。最后一个产生可定价结果的配对决定本次撮合的统一成交价。`price is None` 的断言位于恢复之前。 [固定的撮合源码](../../../vendor/pams/pams/market.py#L1059)
2. 暂取阶段对堆使用 `heappop`，每次弹出均维持剩余队列的堆性质。该阶段只读订单的排序字段。正常通过 `_add_order` 入簿的订单由市场单调分配唯一 ID，并在挂单时写入 `placed_at`。同侧优先级按市价单优先、限价方向、时间和 ID 确定。限价买单以高价优先，卖单以低价优先，时间和 ID 以较小者优先。适用条件是有限限价、正常分配的 ID、继承的 PAMS 比较器，以及没有外部代码在撮合时改写活跃订单的比较字段。 [订单比较器](../../../vendor/pams/pams/order.py#L194) · [入簿源码](../../../vendor/pams/pams/market.py#L921) · [Python 3.12 heapq](https://docs.python.org/3.12/library/heapq.html)
3. 每次压回同一订单对象，两个合法堆最终各自具有相同的订单集合。由于同侧订单具有确定的全序，后续弹出顺序、堆顶和按订单身份定位的行为一致。物理堆数组允许不同。上游成交减量，撤单、过期与 TTL 索引维护继续使用原 `OrderBook`，成交费用、市场历史和日志继续由 `_execute_orders` 更新，资金和持仓继续由 `Simulator` 更新。 [订单簿实现](../../../vendor/pams/pams/order_book.py) · [成交更新](../../../vendor/pams/pams/market.py#L852) · [账本更新](../../../vendor/pams/pams/simulator.py#L243)
4. 支持范围内的观察按原事件产生顺序比较，簿快照按继承的比较器排序。原 `SequentialRunner` 负责代理选择、订单分组处理和高频代理插入，`_process_order` 在原位置触发回调、撮合及账本更新。该适配发生在单市场撮合内部。PAMS 论文给出平台背景，离散事件仿真文献说明保持因果顺序的原因，具体调用顺序以固定源码为准。 [原串行入口](../../../vendor/pams/pams/runners/sequential.py#L561) · [PAMS 论文](https://arxiv.org/abs/2309.10729) · [Chandy–Misra](https://doi.org/10.1109/TSE.1979.230182) · [Fujimoto](https://doi.org/10.1145/84537.84545)

## 最小行为差异

下面是 `Market._execution` 进入增量分支后的恢复段差异。适配类另加模式分派和未知模式检查，局部类型标注使用 Python 3.12 写法。完整方法级 diff 由实际安装的上游函数和生产适配函数生成。 [实际方法 diff 与文件校验](evidence/P05-integration.txt) · [生产适配代码](../../../src/coreorder/market_adapter.py)

```diff
-        # TODO: faster impl
-        self.buy_order_book.priority_queue = [
-            *popped_buy_orders,
-            *self.buy_order_book.priority_queue,
-        ]
-        self.sell_order_book.priority_queue = [
-            *popped_sell_orders,
-            *self.sell_order_book.priority_queue,
-        ]
-        heapq.heapify(self.buy_order_book.priority_queue)
-        heapq.heapify(self.sell_order_book.priority_queue)
+        # Collect only pops roots, leaving both remaining queues as heaps.
+        for order in popped_buy_orders:
+            heapq.heappush(self.buy_order_book.priority_queue, order)
+        for order in popped_sell_orders:
+            heapq.heappush(self.sell_order_book.priority_queue, order)
```

对每侧，令 `n` 为暂取前堆长，`k` 为暂取数，`h=n-k` 为余堆长度。上游为新列表拼接 `n` 个引用并线性建堆，代价为 O(n)。增量恢复沿堆路径插入 `k` 次，堆调整至多 O(k log max(n, 2))，按摊销计算列表追加。小堆或较大的 `k/n` 下仍需实测，两个模式均固定执行所选策略。该上界与比较次数只描述恢复阶段的算法工作量。

PAMS 0.3.0 来源 SHA 为 `6cd53810103780770c5b5d6ee0069ccab9f4b358`。适配方法衍生自该提交的 `pams/market.py`，采用 EPL-1.0 并保留上游署名和许可证。源文件从锁定子模块读取，参与验证的五个已安装 PAMS 模块与之逐字节相同。测试场景依据成员 A 分发包 `common/evidence/platform/pams_heap_restore_probe.py` 重新构造和运行。 [来源锁](../../../UPSTREAM.lock.json) · [PAMS 许可](../../../licenses/PAMS-EPL-1.0.txt) · [上游署名](../../../vendor/pams/CITATION.cff)

## 诊断与复现

`--heap-diagnostics` 为每次进入恢复阶段分别记录买卖侧的 `restore_calls`、`heap_length_before`、`popped_count`、`heap_length_remaining` 和 `restore_fraction=k/max(n,1)`，逐行核验 `n=h+k`。它同时统计两条恢复路径实际调用的 `heapify` 和 `heappush`。过期清理、撤单和建簿调用的堆操作具有各自的调用点。

`--count-heap-comparisons` 独立计数两侧恢复阶段的 `Order.__lt__`。运行使用既有 CPython 3.12 环境，按函数代码对象识别恢复调用点。两个开关默认关闭，开启任一开关时输出 `heap_diagnostics.json`。采集限于仿真线程、仿真运行区间，退出时恢复原 profiler。以下运行属于正确性和诊断证据，记录的仿真时长包含项目观察器开销。 [采集实现](../../../src/coreorder/heap_diagnostics.py)

```sh
.venv/bin/python -m coreorder run --backend py-seq --book-restore upstream \
  --config configs/workloads/smoke.json --seed 42 --output results/p05-upstream \
  --heap-diagnostics --count-heap-comparisons
.venv/bin/python -m coreorder run --backend py-seq --book-restore incremental \
  --config configs/workloads/smoke.json --seed 42 --output results/p05-incremental \
  --heap-diagnostics --count-heap-comparisons
.venv/bin/python -m pytest -v -s tests/heap
```

诊断测例由同一份 CI2002 smoke 配置改用 PAMS 的 `extends` 表达市场组，seed 42。两条路径各发生 12 次恢复，逐次大小与比例相同。p90 采用最近秩，p50 用中位数。

| 侧 | Σn | Σh | Σk | 比例 min / p50 / p90 / max | 原版 / 增量恢复比较次数 |
| --- | ---: | ---: | ---: | --- | ---: |
| 买 | 268 | 242 | 26 | 0.0690 / 0.0851 / 0.2000 / 0.3077 | 433 / 97 |
| 卖 | 233 | 207 | 26 | 0.0870 / 0.0909 / 0.1818 / 0.5000 | 377 / 93 |

上游两侧合计执行 24 次恢复 `heapify`。增量调用 52 次 `heappush`，恢复 `heapify` 为 0。两条路径的这组运行均为 80 条下单、14 笔成交。该计数支撑此工作负载的恢复机制分析。端到端性能和硬件 cache 行为是 NOT_RUN。

## 本地正确性与复验

本轮以 P04.5 `835de4755b253a63b709b7a4cc446141a2ca8f46` 为基线，接回原 P05 `29042c469e74c4391f128ff88b94e5a138633878`。在干净源码 `3effd9afd4ae9887adb398086e13ad885fadd463` 上运行，环境为 macOS ARM64、CPython 3.12.13 与项目锁定依赖。原 P05 证据随提交保留。 [本轮命令、退出码与方法 diff](evidence/P05-integration.txt) · [原 P05 日志](evidence/P05.txt)

| 检查 | 实测结果 |
| --- | --- |
| A 侧全仿真 | 8 对探针复跑覆盖 fixed/normal、短/长窗口与 TTL、seed 42/20261125。CI2002 smoke 和 event-state 各用 seed 101/202/303/404/505，另通过 10 对。两条路径逐事件、逐步市场、账户、逻辑簿、市场历史和最终完整 RNG 一致。event-state 的五个种子均为零成交、20–22 笔过期。 |
| E 采集器复验 | 从 E 的固定 Git 提交 `b05d555` 读取 `C01a-M1`、`C01b-normal` 和 `C01g-fundamental-shock` 原配置字节，各用 seed 101/202/303/404/505，15/15 对通过。独立进程从核验过的 vendor 运行原版，生产串行入口调用实际增量堆，沿用 E 的只读观察器和结构比较器。候选逐帧只移除属于运行元数据的 `book_restore` 字段，其余初态、终态、事件和完整 RNG 逐结构比较。 |
| 定向订单簿 | 9/9 通过。覆盖部分成交和多价位、同价同时间按 ID 排序、市价和限价、无可定价、撤单、过期、不交叉、后续新单与原断言位置。核验余堆合法、原对象身份及实际后续出堆顺序。 |
| 恢复调用点 | 撤单到期用例中，两条路径各有 2 次建簿、1 次非堆顶移除、1 次到期清理的原版 `heapify`。恢复段从 2 次 `heapify` 降为 0。CI2002 smoke 的恢复和比较器计数见上表。 |
| 集成回归 | 项目 pytest 80/80、根 CTest 2/2、上游指定 35/35（302 项未选），`pip check` 通过。G0 的 `validate --suite smoke` 与 `--suite g0` 均以 0 退出。 |

A 侧完整仿真使用 `SequentialRunner.main()` 参考路径，任一语义文件出现差异时生成 `first_divergence.json`，保存首行、字段、seed 和两侧状态及最终 RNG 的引用。E 比较器按原产生顺序比较事件，并对各侧订单簿用原比较器规范化。E 的代表样本对照保留重放所需配置、原版与候选 trace 和比较结果。 [A 配对和首差回归](../../../tests/heap/test_heap_runs.py) · [定向边界](../../../tests/heap/test_market_adapter.py)

原始产物位于 `results/acceptance/p05-integration/`。`pytest-artifacts/` 保存 A 配对及诊断输出，`c01-representatives/` 保存 E 观察器的代表样本及逐案回执。`audit_restore.py` 和 `audit_c01.py` 对应调用点与独立 C01 复验。P05 状态为 **MODULE_PASS**。正式 G1-heap 签认留给对应阶段，端到端性能与硬件计数为 **NOT_RUN**。
