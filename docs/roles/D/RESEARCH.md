# 成员 D 研究记录 · R4

## D1　沿上游函数确定工作集

本次读取 PAMS 0.3.0 的固定提交 `6cd53810103780770c5b5d6ee0069ccab9f4b358`。下载固定 SHA 的 GitHub tarball，在项目外解压，保留其 EPL-1.0 许可证。归档 SHA-256 为 `6a7fca20ab43d3c6efc00c6ba171050e353b80300a8771ac490134500bce5297`。另用固定 SHA 的 Taskflow 3.11.0 头文件检查 worker 如何消费索引。FCN、撮合、随机分布和调度算法均沿用各自上游的作者归属。[PAMS 固定源码包](https://api.github.com/repos/masanorihirano/pams/tarball/6cd53810103780770c5b5d6ee0069ccab9f4b358) · [PAMS 许可证](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/LICENSE)

| 实读文件 | 内容哈希 SHA-256 | 约束 |
|---|---|---|
| PAMS `pams/agents/fcn_agent.py` | `e8b6d9b642042c0de25099ca41691923463c17a09e231c6c47ce1312ce825922` | 市场顺序、可访问性、两类窗口和随机样本 |
| PAMS `pams/market.py` | `5d97291fc216d6e7c2691058dddaffe6f3ba7a7f7ff0a435e17c92aef88b1e1a` | 当前时刻、历史价及基本面 getter |
| Taskflow `taskflow/algorithm/for_each.hpp` | `7f21fdfc7a0aad4f177f0343bda6a9fead2f6bc9388b939368ccce90d6955dc0` | 半开区间内的索引，worker 与数据所有者的关系 |

`FCNAgent.submit_orders` 按传入 markets 顺序逐市场调用。每次调用先依据 `market_id in self.asset_volumes` 判断访问权限。不能把资产数量为零误读为不可访问。在可访问分支，函数读取该市场的时刻、当前市场价、当前基本价、截短窗口起点的市场价。历史的索引边界来自 `min(time, time_window_size)`，预测期与订单 TTL 仍用配置的 `time_window_size`。原实现多次读取当前价；只对已验收的无副作用市场类型将同一批内的一行压缩为三个价格值。FCN 文件第 137–209 行可核对 fixed 的一次 gauss 和 normal 的两次 gauss，后者先于是否有订单的比较。D 消费 A 传来的原样本，不推进 agent.prng。[FCN](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/agents/fcn_agent.py#L114-L237) · [访问权限](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/agents/base.py#L170-L180) · [市场历史](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/market.py#L167-L223)

在固定 Taskflow `816b4ad53b44196c88f409eb7b4a25a0e3bfdf42` 的 `make_for_each_index_task` 中，小范围走本地索引循环，静态分区按 chunk 取半开区间，动态分区用共享原子游标分配区间。实现以索引调用用户回调，未规定回调读取 AoS 或 SoA。D 交出稳定的只读缓冲区。B 以同一个公式消费每行，C 划分写入区间并等待全部任务结束。D 文档/测试仅引用上游接口，未搬入 MIT 头文件或 BSD-3-Clause 的 pybind11 源码。[Taskflow 源码](https://github.com/taskflow/taskflow/blob/816b4ad53b44196c88f409eb7b4a25a0e3bfdf42/taskflow/algorithm/for_each.hpp#L74-L144) · [Taskflow 许可证](https://github.com/taskflow/taskflow/blob/816b4ad53b44196c88f409eb7b4a25a0e3bfdf42/LICENSE) · [pybind11 许可证](https://github.com/pybind/pybind11/blob/a2e59f0e7065404b44dfe92a28aca47ba1378dc4/LICENSE)

## D2　布局对照设计

每个可访问 agent–market 对产生一个输入行。两布局储存相同 15 个原始字段，输出和回填元数据也相同。连续 AoS 的同字段步长为 112 字节；SoA 的同字段步长等于该标量宽度。跨行访问相同字段时可利用 SoA 单位步长。逐行读取大量不同字段时，多条列流可能减弱同一行的局部性并增加 TLB 压力。是否有净收益取决于实际的访问顺序、生成代码和工作集，需独立测量。[Intel 布局变换](https://www.intel.com/content/www/us/en/developer/articles/technical/memory-layout-transformations.html)

Roofline 的运算强度需要与测量层级相符的流量。数组的 `nbytes` 适合核对逻辑有效数据与保留容量，无法据此推出内存控制器处的字节数。Linux 目标应记下 perf 的具体事件、采集范围与可用计数时间，再按 decision_rows 归一化。通用事件名不足以定位到 LLC；Cachegrind 的模拟数据应独立标注。上述是后续测量可检验的假设，D1–D3 未进行正式缓存归因。[Roofline 技术报告](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2008/EECS-2008-134.html) · [perf stat](https://man7.org/linux/man-pages/man1/perf-stat.1.html) · [Cachegrind 手册](https://valgrind.org/docs/manual/cg-manual.html)

## D3　验证状态刷新

测试对真实 PAMS 的 agent 和市场做两次连续调用。第一次包含有访问权且不下单的 normal agent、只访问一个市场的 fixed agent 和完全不可访问的 agent。第二次修改窗口、方向、权重、margin 和市场历史，用同一个缓冲池生成新批次。完整比较 agent RNG（含 gauss 缓存），核对调用序号跨过空 agent 后仍然原样保留。测试中用独立 Random 复核已经由上游实际调用的随机序列，该操作只存在于测试。

公共 fixture 来自 A 在固定 PAMS 上用 seed 42 采集的 fixed/normal 24 行。其 `fcn/rows.jsonl` SHA-256 为 `c7bd6c091b008534c8b0978128b41141acd3cfb643de0ee95165c12a0002c6aa`。将所记录的可观察状态重建在真实 PAMS 对象中，对两种布局逐字段核对，每个浮点比较 `float.hex()`。这种重放检验 D 的物理输入与元数据；跨 worker 的事件顺序和最终随机状态由 A/C/E 在系统装配后验收。运行方式及实际结果见 STATUS。

## 来源和许可

成员 D 的 packing 与布局适配按团队约定使用 EPL-1.0。PAMS 模型及原版 FCN 的作者归属保持不变。D 的修改范围是抽取实时字段、按 R4 存储及验证物理布局。原许可随附于 [EPL-1.0.txt](EPL-1.0.txt)。B 的数值代码和 A 的 fixture 通过上表的固定快照参加验证。PAMS、Taskflow 和 pybind11 的源码不随本分支重新分发。
