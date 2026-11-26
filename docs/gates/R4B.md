# R4B · x86 正式正确性与 G3 冻结审查

**C01 与 V01 技术验收均为 PASS。G3 保持 BLOCKED，等待当前候选的共同门禁和独立签认。**

受测代码为 `58ec5764c21833142c50abacd9e2302404ffdb06`。正式计时授权为空。

## 验证实现与受测身份

R4A 的 W0 同进程比较以及 W1–W3 完整 oracle 触及 7 GiB 保护上限。R4B 让独立 PAMS oracle 和同一生产执行器逐帧落盘与读取。原逐事件、逐步市场与账本状态、历史、初态、终态及完整 RNG 仍参加精确比较。每个新的 Python MT19937 词组以 624 个原始无符号字存储。检查点保留该词组引用、原始索引和 Gaussian cache，NumPy RNG 保留其原始显式编码。流式轨迹的实际 PAMS 回归可无损重建旧格式，并能检测单字的 RNG 损坏。守恒及成交、挂单和账本一致性检查复用 E 的原判定。

Linux 原生阶段剖析改为显式计时生产绑定的调用，阶段模式通过了 CPython 3.12.3 实际回归。严重影响 R4A 的 c_call 缺失保留在 R4A 原始记录中。生产数值核、PAMS 金融逻辑、比较阈值、随机流定义和正式无仪器计时边界保持 R3/R2A 口径。

华硕 Ubuntu 24.04.5 WSL2 在干净源码上按锁构建，CTest 7/7，目标机定向 pytest 32/32，本地干净源码全 pytest 169/169。目标机 E1 G0 回归通过事件、逐步状态和完整最终 RNG 核查。目标机实际 C++ 编译参数含 `-O3 -fno-fast-math -ffp-contract=off`。加载扩展 SHA-256 为 `a9d294e6bac9098bb486d1ba3e728a0fa9f974eb858ad107fde858b86e16fc5e`。R4B 本地首次平台测试与代码提交发生重叠，实验执行器拒绝跨 SHA 继续绑定。原日志保留，随后在固定干净 SHA 上重跑通过。

[受测身份](evidence/R4B/candidate-identity.json) · [目标构建与测试](evidence/R4B/build-x86.log) · [目标 E1 G0 回执](evidence/R4B/target-g0-receipt.json) · [编译命令](evidence/R4B/compile_commands.json) · [本地干净回归](evidence/R4B/local-pytest-clean.log) · [首次身份拒绝](evidence/R4B/local-platform-identity-interrupted.log)

## 批准后的科学对照

原 P12 文件校验通过。固定 pilot seed 11 的完整长 W1 测得 oracle 172.29 s、候选 176.41 s，仅该原配置的 5 个参考和 30 个候选外推已超过整个 V01 的 80 min。已存在的 W1-H 在保持 N=4096、M=32、K=1 条件下，完整 20+100 步参考和候选分别耗时 35.27、37.98 s。组长已批准采用该现有配置作为 E02 小批次，并移除 W1/W3 额外的 8-worker 点。W2-MEDIUM-BATCH 的独立参考和候选分别耗时 153.70、67.16 s。组长又批准 E03/E05 复用同 N/M/K 的 W2-H 原 8+24 步。W3 保留 2+8 步，首次探测被剩余校准预算截断。独立补测 oracle 72.32 s、候选 34.96 s。结合全部探测，原版 V01 外推 184.06 min，仅缩减 W1 与 8-worker 的版本外推 91.25 min，最终批准的版本外推 **60.63 min**。这些估计使用每个工作负载与角色的一条验证观测。选择依据为完整验证成本与核心对照覆盖。

| 组 | 经批准的保留内容 |
| --- | --- |
| C01 | 原 420 条，原 12 类短场景与全部五 seed。清单逐字节保留。 |
| H01 | W0-H、W1-H、W2-H。每组固定 `py-seq` 和相同 workload，仅改变 heap restore。 |
| E01 | 固定 vendored CI2002 和 upstream heap。原版顺序 PAMS、PAMS 线程/进程及原生对照。 |
| E02 | W1-H、W3。相同 incremental 条件下保留 Python、direct native、Taskflow 1/2/4。 |
| E03 | W2-H、W3。分别对 direct 及同一 4-worker、static、grain 128 的 Taskflow 只改变 AoS/SoA。 |
| E05 | 4 个 profile、24 个已支持 PMU 事件组的诊断运行，48 个使用 W2-H 真实输入的 replay。LLC 专用事件缺测。 |
| V01 / timing | 125 个唯一候选、20 个独立参考。435 个配对 timing 加 58 个预热。 |

W1-H 的同条件完整 V01 可跨 H01/E02 引用，同一 seed 的性能观测仍按各自预先定义的区组配对。E01 的原版比较与 E02/E03 的最终组合目前分属不同对照。最终论文只能报告有直接同配置证据的效果。

统计固定为五个正式 seed 101、202、303、404、505，三个随机顺序配对重复、每变体两个预热。单位为 seed，10,000 次 bootstrap、95% 区间，缺测不补值，TIMEOUT 保留右删失。候选硬预算仍是 P01 30、C01 40、V01 80、E01 45、H01 55、E02 105、E03 70、E05 35 min，另预留 20 min，共 480 min。

[原计划哈希检查](evidence/R4B/p12-hash-check.log) · [批准方案清单生成脚本](evidence/R4B/revise_candidate.py) · [组长决定](evidence/R4B/leader-decisions.json) · [最终预算核算](evidence/R4B/budget-approved.json)

## 同版本签认查询

组长已批准无费市场范围、显式拒绝及手动选择 py-seq。GitHub 查询只找到旧 G0 草稿 PR 和成员 E 的模块交付。PR 未提交 review，E 分支明确将集成门禁标为待完成，受测 SHA 的托管 PR 流水线查询也为空。本阶段的 E 工具 PASS 由原始差分和可重算回执支持。团队签认由对应复核人对实际凭据确认。

[GitHub PR #1](https://github.com/DengJunxian/CoreOrder/pull/1) · [成员 E 交付](https://github.com/DengJunxian/CoreOrder/blob/b05d5555fa5cc756a91ab61c644e797ca227c26f/docs/roles/E/STATUS.md) · [查询证据](evidence/R4B/github-review.json)

## 目标主机的正式正确性批次

C01 按原清单执行，60 个独立上游参考和 360 个生产候选全部通过。实际墙钟 **2 分 15.74 秒**，封存原始文件共 73,512,376 B。V01 对最终保留的 25 个不同条件逐一覆盖五个正式 seed，20 个独立参考和 **125 个生产候选全部通过**。实际墙钟 **64 分 26 秒**，峰值常驻内存约 1.33 GiB，原始文件共 12,784,541,055 B。没有 TIMEOUT、FAIL 或缺失的正式验证单元。原先 W3 校准的右删失记录单独保留。

复核重读全部封存文件并重算 SHA-256，逐项核对实际主机、源码/上游、原生扩展、Python/依赖环境、原始与有效配置、backend/heap/layout/workers/grain/schedule、seed、E 差分和不变量回执。493 条计时计划均可追溯到一个实际通过的同配置 V01 ID。C01 原始计划与 V01 的审查前计划分别保存身份，执行批次的哈希未被后续文件更改重写。

[C01 命令日志](evidence/R4B/c01.log) · [C01 原始索引](evidence/R4B/c01-index.json) · [V01 命令日志](evidence/R4B/v01.log) · [V01 回执与证据索引](evidence/R4B/v01-index.json) · [目标封存复验](evidence/R4B/final-audit-x86.log)

## E05 准备与 G3 状态

华硕三组事件沿用已通过的 CPU、L1D 和分支定义。用户态 perf 6.8.12 的实际路径及 SHA-256 已重新核对。LLC 缺测继续登记。Replay 在 seed 11 上按三个前缀、两布局、direct 和 4-worker 条件校准，固定共同重复次数 3,000，绑定区间实测 **0.185–0.826 s**。正式输入来自 W2-H seed 101 的生产绑定原序 8,192 行，匹配 V01 run ID `6d10cadf6ca44b87b8e40221f4e24bea` 的金融终态和 RNG 摘要。保留输入和对应回执，可凭内容哈希复验。

| 验收项 | 状态 |
| --- | --- |
| 同版本 x86 定向构建、E1 G0 技术回归及 E 副本回归 | **PASS** |
| C01 全矩阵、V01 全板及原始证据复验 | **PASS** |
| 计时计划与全部 V01 回执关联、E05 硬件事件与 replay 输入资格、文件校验 | **PASS** |
| 共同 G0/G1/G2、E 及非作者的同版本团队签认、G3 生效 | **BLOCKED** |
| 正式计时和 E05 正式采集 | **NOT_RUN** |

R4B 候选交付位于 `configs/experiments/r4b`。协议文件可以从独立文档提交部署到目标机外部计划目录，目标机保持受测版本和同一个实载二进制。被冻结前的计划、受测源码、封存验证批次和待签版本各有独立摘要。R4B 审查包的候选身份为 `8113c98d7c108b8fd33dd86d35c7c63e890cf6f05fd731ded36551c26ce0219c`。形式化生效前需对该受测源和这些回执完成真实的共同门禁与独立签认，并登记签名所对应的最终生效锁摘要。G3 防护测试实测返回 2，正式运行目录未创建。

[Replay 输入回执](../../configs/experiments/r4b/replay-source/capture-receipt.json) · [校准记录](evidence/R4B/calibration-summary.json) · [PMU 工具身份](evidence/R4B/pmu-tool-identity.log) · [frozen.json](../../configs/experiments/r4b/frozen.json) · [protocol_lock.json](../../configs/experiments/r4b/protocol_lock.json) · [文件校验和](../../configs/experiments/r4b/R4B-SHA256SUMS) · [候选最终复验](evidence/R4B/final-candidate-audit.log)
