# R5B 图表、原始数据与复算

公开分支用占位符保留原始文件定位的结构。此处随附的文件校验清单对应公开副本，原实验文件的身份仍见内部封存。 [公开镜像说明](../../../PUBLIC_HANDOFF.md)

[科研结果、适用范围及 RQ 证据矩阵](../../R5B.md) · [散列清单](SHA256SUMS)

## 已生成的表和图

| 产物 | 数据版本、样本和单位 | 范围及原始定位 |
| --- | --- | --- |
| 正确性验收 [PDF](artifacts/validation/correctness.pdf) / [PNG](artifacts/validation/correctness.png) / [CSV](artifacts/validation/correctness.csv) | R4B x86，受测提交 `58ec5764c21833142c50abacd9e2302404ffdb06`。C01 420 次、V01 145 次，单位为运行次数。 | 有序事件、状态检查点、账本和 RNG。两个索引包含 case ID、run ID、实际命令、原始目录、封存哈希及生产候选回执。[C01](../R4B/c01-index.json) · [V01](../R4B/v01-index.json) |
| 硬件与负载 [PDF](artifacts/validation/configuration.pdf) / [PNG](artifacts/validation/configuration.png) / [主机 CSV](artifacts/validation/hardware.csv) / [负载 CSV](artifacts/validation/workloads.csv) | 一台华硕 x86。R4B 的 25 个唯一候选条件、每条件 5 个 V01 seed。Cache 单位为 KiB/MiB，负载为智能体、配额、市场和步数。 | 环境说明表，无采样时间。[Windows 与来宾拓扑、PMU](../../R4A.md) · [现场环境](../R4B/environment.json) · [编译命令](../R4B/compile_commands.json) · [候选 workload](../../../../configs/experiments/r4b/frozen.json) |
| 堆恢复工作量 [PDF](../../../roles/A/evidence/P13/figures/heap-mechanism-pilot.pdf) / [PNG](../../../roles/A/evidence/P13/figures/heap-mechanism-pilot.png) / [CSV](../../../roles/A/evidence/P13/figures/heap-mechanism-pilot.csv) | P11 Apple M5 pilot，源提交 `3c344f765c6ff288abad2faa6081c921f0ee0f36`。3 个 workload × 2 seed × 两种恢复方式，逐侧统计。单位为比较次数、订单条数、恢复比例。 | 比较器计数诊断。复用 P13 已验图及脚本。[原始定位及复算](../../../roles/A/evidence/P13/INDEX.md) · [逐侧数据](../../../roles/A/evidence/P11-heap.csv) · [生成脚本](../../../roles/A/evidence/P13/figures/gen_fig_heap_mechanism.py) |
| x86 工作集 replay [PDF](artifacts/pilot/replay-calibration.pdf) / [PNG](artifacts/pilot/replay-calibration.png) / [CSV](artifacts/pilot/replay-calibration.csv) | R4B pilot，源提交 `58ec5764c21833142c50abacd9e2302404ffdb06`。W2-H seed 11，三个真实输入前缀、两布局及两执行器，共 12 次启动，每点 1 次。单位为 KiB 和 ns/行。 | 每点 3,000 次复用同一前缀，包含生产绑定、输出分配和 Taskflow 任务等待；SoA 拆列在计时前。nominal 口径为前缀行数 ×（112 B 输入 + 16 B 单份输出）。[12 条 raw 及命令哈希](replay-raw-index.json) · [生产 replay 入口](../../../../experiments/replay.py) |
| Packing、原生绑定与瓶颈迁移 [PDF](artifacts/pilot/instrumented-spans.pdf) / [PNG](artifacts/pilot/instrumented-spans.png) / [CSV](artifacts/pilot/instrumented-spans.csv) | P11 Apple M5 pilot，源提交 `3c344f765c6ff288abad2faa6081c921f0ee0f36`。W1-H seed 11，三条运行，每条 1,211 次恢复区段、120 次决策区段，direct 的展示子区段各 120 次。单位为累计秒，轴为对数尺度。 | A 面板为恢复和智能体选择／决策的包含式区段。B 面板为 direct 决策内部分区段，含 binding 而非纯内核。[原始阶段文件哈希](p11-phase-raw-index.json) · [P11 阶段源数据](../../../roles/A/evidence/P11-phases.csv) |
| 正式对照覆盖 [CSV](artifacts/formal-pairing-coverage.csv) | R4B 候选冻结清单，19 个比较 × 15 个计划配对，0 个有效配对，单位为候选配对位置。 | 每行由候选 group、workload、baseline 和 variant 定位。NA 表示无数据。H01/E01/E02/E03 的正式性能图缺测。[runlist](../../../../configs/experiments/r4b/runlist-timing.jsonl) · [候选计划](../../../../configs/experiments/r4b/frozen.json) · [目标机库存日志](x86-inventory.log) |

正式 E05 阶段量测与硬件计数均缺测。实际 PMU 事件能力、工具和权限以 R4A/R4B 的记录为准，LLC 保持缺测。[PMU 能力表](../../R4A.md#pmu-能力与-cache-机制证据) · [R4B perf 工具身份](../R4B/pmu-tool-identity.log)

## 复算

从仓库根目录运行，Python 3.12、Matplotlib 3.11.2。脚本写入新目录，输出包括矢量 PDF 和 300 dpi PNG。候选 W0 源文件位于固定 PAMS 子模块。

```sh
git submodule update --init vendor/pams
review_dir="$(mktemp -d)"
python -B docs/gates/evidence/R5B/generate_review.py --output "$review_dir/artifacts"
diff -r docs/gates/evidence/R5B/artifacts "$review_dir/artifacts"
(cd docs/gates/evidence/R5B && shasum -a 256 -c SHA256SUMS)
```

脚本验证候选和 R5A 证据校验和、两套验收清单覆盖、验证回执序列化摘要、原始配置与规范化身份、源版本和主机。目标机原始验证封存的逐文件复验见 [R4B 审计脚本](../R4B/audit_batch.py) 和 [R5A 准入复验](../R5A/preflight-x86.py)。pilot 工作集的制图镜像必须与归档校准汇总逐单元相符。Apple M5 的可移植阶段表与三份原始文件的核对保存在本目录。已有 P13 堆图由它自己的脚本复算。

正式采数后，使用仓库已有 `python -m analysis.report`，传入生效协议目录、封存 timing 目录和匹配的 `--receipts` V01 目录，按同一身份附上 `--diagnostics` E05 目录与 `--figures`。该命令核对正式锁、批次作用域、真实 backend、终态和 RNG 与回执的绑定，以及配对与删失状态。R5B 实测将 candidate-validation 批次送入该正式入口时被拒绝。

[本轮统计与协议测试](statistics-tests.log) · [图表生成日志](generation.log)
