# CoreOrder 实验结果

华硕 x86/WSL2 的独立组长授权实验包含 465 条有效低开销计时、62 条计时预热、79 条 E05 记录。25 组主要对照覆盖 375/375 个配对位置。C01 与 V01 分别完成 420/420 和 145/145 次独立正确性尝试。原 A/E 双人 G3 保持 `BLOCKED`。

| 数据 | 文件 |
| --- | --- |
| 五 seed 配对效应、95% 区间和并行效率 | [效应表](effects-with-efficiency-ci.csv)、[逐 seed 效应](seed-effects.csv) |
| 各计时端点的中位数和 IQR | [绝对时间](endpoint-descriptives-seconds.csv) |
| 应用阶段剖析及合格 PMU 计数 | [阶段](e05-profile-phases.csv)、[逐事件计数](e05-pmu-events.csv)、[同次启动比率](e05-pmu-ratios.csv) |
| 真实捕获输入回放及生产批次 | [E05 回放汇总](e05-replay-summary.csv)、[T05 实际批次和 range](../gates/evidence/T05/analysis.json) |
| CI2002 单次多进程传输诊断 | [回执](spawn-diagnostic/receipt.json)、[队列测量](spawn-diagnostic/process_copy.json) |
| 正确性回执索引 | [C01](../gates/evidence/R4B/c01-index.json)、[V01](../gates/evidence/R4B/v01-index.json) |

W2-H 同区组下，heap-only、四 worker AoS、四 worker SoA 的仿真速度比分别为 16.704×、13.266× 和 13.143×。公开表格保留有效配对的派生统计和原始标识。目标机封存的全量轨迹、激活用协议和原始回执由团队保管。流程见[实验说明](../EXPERIMENTS.md)，发布范围见[最终审计](../gates/FINAL.md)。

[综合对照](../gates/evidence/F4/figures/system-forest.pdf) · [堆恢复](../gates/evidence/F4/figures/heap-work-and-speedup.pdf) · [多核与效率](../gates/evidence/F4/figures/native-scaling-and-efficiency.pdf) · [AoS/SoA](../gates/evidence/F4/figures/layout-forest.pdf) · [瓶颈迁移](../gates/evidence/F4/figures/phases-and-bottleneck.pdf)
