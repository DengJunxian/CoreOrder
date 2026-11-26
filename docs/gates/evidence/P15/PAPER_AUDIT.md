# 论文、统计与课件证据核对

审查了 A 的 P14 正文与答辩、B/C/D 的实际分支方法稿和 E 的 E1–E3 方法及统计框架。完整团队论文、合并课件和正式结果图未取得。 [A 论文](../../../roles/A/p14/PAPER_DRAFT.md) · [五人来源](CONTRIBUTIONS.md)

| 论断 | 判定 | 核对结果 |
| --- | --- | --- |
| C1 · 平台语义 | **PASS（方法及本机）** | PAMS 保留原调度、提交、撮合、账本、HFT 与市场事件。核对配额按非空代理计、可访问市场原序和 Gaussian 缓存。P10 56/56 与 P15 18/18 仅覆盖受测范围，正式 G2/V01 仍 BLOCKED。 [固定 PAMS](https://github.com/masanorihirano/pams/tree/6cd53810103780770c5b5d6ee0069ccab9f4b358) · [批次代码](../../../../src/coreorder/native_serial.py) · [差分回执](reproduction.json) |
| C2 · 堆恢复工作量 | **PASS（方法及 pilot）** | 收集阶段确定 pending 和统一价，恢复同一对象和严格优先序。单侧原版 `O(n)`，逐项堆调整最坏 `O(k log(n+1))`，列表扩容另按摊销。W1-H seed 11 两侧合计从 1,710,577 至 38,953 次，W2-H 从 8,245,535 至 92,206 次。单位、负载、机器、种子和原始工作量可核。 [恢复源码](../../../../src/coreorder/market_adapter.py) · [图表数据](../../../roles/A/evidence/P13/figures/heap-mechanism-pilot.csv) |
| C3 · 原生化 | **PASS（方法） / NOT_RUN（正式速度）** | 112B/16B ABI、严格浮点和 direct loop 有生产证据。P11 W2-H、W3-START 的 native-serial 未进一步降时，W4 两 seed 方向不同。B 的模块短批和 C++ 核 replay 保留各自测量边界。 [ABI 门记录](../../G2.md) · [pilot 运行表](../../../roles/A/evidence/P11-runs.csv) |
| C4 · 多核扩展 | **PASS（机制） / NOT_RUN（正式速度）** | 同一 B 核、Taskflow 持久池、独占槽及 barrier 有真实证据。p=1 executor 与 direct loop 各自运行。E04 默认关闭。C 草稿的 GIL 和进程序列化论述应匹配受测 Python 工作与已记录拷贝，整机效应待受控对照。 [运行时](../../../../native/runtime/executor.cpp) · [实际集成](../../G2.md) |
| C5 · 布局与 Cache | **PASS（布局） / NOT_RUN（硬件效果）** | 两布局字段相同，AoS 112 B 行步长与 SoA float64 8 B 列步长有实测。缓存、带宽和伪共享结论缺 PMU。E03 保持公式、工作量与 workers，E05 需定义事件与作用域，并记录有效采样。 [布局证据](../../G2.md) · [Intel 布局文档](https://www.intel.com/content/www/us/en/developer/articles/technical/memory-layout-transformations.html) |
| C6 · 瓶颈迁移 | **PASS（本机剖析） / NOT_RUN（正式推断）** | W1-H seed 11 原版 heapify 约 2.499 s / 2.903 s，增量 `Random.sample` 约 0.151 s / 0.473 s，即约 32%。专属恢复时长来自另一套探针。Amdahl 是指定可并行比例下的理想上界。保留两次计数超时及复跑。 [P11 计时口径](../../../roles/A/RESULTS.md) · [Amdahl 原文](https://www.cs.cmu.edu/~18742/papers/Amdahl1967.pdf) |
| C7 · 可复现性 | **PASS（本机） / NOT_RUN（第二设备）** | 同机干净克隆、三次真实 Demo 和原始回执可查。正式主机、独立人员、跨 ISA/libm、热状态与硬件事件限制外推。 [实跑证据](DEMO.md) |

候选 H01 仅切换恢复方式，E02 固定增量堆比较原生化和多核，E03 固定公式与 workers 比较布局。正式 seed 是 101、202、303、404、505。按区组算 log-ratio，每 seed 取 3 次技术重复中位数，按 seed 等权聚合。10,000 次 bootstrap 以 seed 为单位，随机种子 73021。清单和哈希复校通过，正式分布、区间和效果仍未测。 [G3 规划](../../G3.md) · [Kalibera 与 Jones](https://kar.kent.ac.uk/33611/)

P13 左面板为单侧恢复比例中位数与第 99 百分位，右面板为双侧恢复比较，纵轴为对数。P12 图单位为实际事件数。两张图及相关数据文件从 raw 重建，五个文件与归档字节相同。P14 两张方法图示执行边界和经 `heapq` 核对的示例，小堆序号用于讲解。A 的两页实际 PPTX/PDF 与原图数据一致。 [重建回执](figure-audit.json) · [两页 PDF](../../../roles/A/p14/A-defense.pdf)

P15 的重建产物位于 `results/acceptance/final/p15/rebuilt-figures/`。P11 先以原项目环境运行 `summarize_p11.py` 并导出五表，P13 的 `gen_fig_heap_mechanism.py` 从该次导出的 `heap-summary.csv` 生成图与表。P12 将原 `raw/` 与 `lineage.json` 置于新目录，运行 `python docs/gates/evidence/P12/audit_chain_p12.py plot <新目录>`。脚本逐项校验 raw 哈希，P15 只调用 plot 入口。两张结果图使用 Matplotlib 3.11.2，输出与跟踪的图、表逐一执行 `cmp`。 [P11 输入和重算命令](../../../roles/A/evidence/P13/INDEX.md) · [P12 绘图入口](../P12/audit_chain_p12.py)

PAMS 是 Hirano、Takata、Izumi 的 2023 年 arXiv 预印本。Chandy–Misra 1979 与 Fujimoto 1990 用于说明因果约束。Taskflow 是 Huang 等的既有运行时，IEEE 卷期为 2022，DOI 标识含 2021。上游平台、经典算法、既有运行时及各成员新增代码的归属已在 A 稿核对。完整论文需在 E 统稿后复验单位、分母、图题、数据范围与作者归属。 [PAMS](https://arxiv.org/abs/2309.10729) · [Chandy–Misra](https://www.cs.utexas.edu/~misra/scannedPdf.dir/DistrSimulation.pdf) · [Fujimoto](https://www.cs.utexas.edu/~browne/cs380ns2003/Papers/p30-fujimoto.pdf) · [Taskflow](https://www.computer.org/csdl/journal/td/2022/06/09511796/1vYRJkLmTDO)
