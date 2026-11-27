# 成员 A 阶段状态

## P01 上游接入与基础工程

| 项目 | 状态 | 证据 |
| --- | --- | --- |
| 三项 Git 子模块、工作树及来源许可 | PASS | Gitlink、检出 SHA 和许可证副本一致，vendor 状态为空。 |
| Python 3.12 安装、依赖及 PAMS 导入 | PASS | `pip check` 退出 0，能导入固定源码构建的 PAMS 与 `SequentialRunner`。 |
| 本机基础测试与 C++17 工具链 | PASS | pytest 4/4，CMake Release 构建成功，CTest 1/1。 |
| G0 与后续金融正确性、性能 | NOT_RUN | 等待对应阶段。 |

P01 基础工程状态为 **PASS**。基线 `e2492a4b8317c6674918b13470b577f4d6f8675d`，分支 `a/01-foundation`，交付 SHA 以包含本回执的提交为准。复现步骤见 [README](../../../README.md)，实际命令和退出码见 [P01 日志](evidence/P01.txt)。

下一阶段输入为已固定的 PAMS 和本地安装流程。P02 的 CI2002 与 `py-seq/upstream` 由 A 接续，独立比较器依 A/E 交接安排完成。

## P02 原版参考与 py-seq

输入基线为 `6ec33312cbc4f98f5e5f24e098aa21745e63669d`，本地分支为 `a/01-foundation`。公共字段按 R4.0 实施，公共 schema 冻结留给下一阶段。

| 检查 | 状态 | 实际观察 |
| --- | --- | --- |
| 官方 CI2002，seed 42 | PASS | 600 步。独立全量 reference 的 600 条市场观察与官方 stdout 一致；reference 记录 600 笔订单、207 笔成交、144 笔过期。 |
| Smoke 及同 seed 重复 | PASS | 24 个代理、1 个市场、80 步、M=1。每次 80 笔订单、14 笔成交，成交量 14。与 smoke reference 的有序交易事件、逐步市场观察、初末账户及最终簿、最终 RNG 一致。 |
| 账户检查 | PASS | 无费配置下总现金初末均为 240,000，总持仓初末均为 1,200，个别账户随交易变动。 |
| 依赖、构建及测试 | PASS | `pip check` 退出 0；上游选测 35 项通过、302 项未选，项目 pytest 11/11，CTest 1/1。 |
| 未实现后端 | PASS | `native-parallel` 返回 2，状态 `UNSUPPORTED`，实际 backend 为空且未启动仿真。项目测试覆盖其余未实现后端及增量恢复拒绝。 |
| G0、完整状态验证与正式性能 | NOT_RUN | P02 记录为诊断样本。 |

执行、配置 hash、重复核验与退出码见 [P02 日志](evidence/P02.txt)。提交 SHA 以包含本回执的本地提交为准。

## P03 公共接口与协作基线

输入基线 `5cc8b5ee8889b4c1ac1e363be0b2be30db5b1281`。A 侧 ABI、schema、真实 fixtures、CLI 接口及 CI 对应命令检查通过。G0 候选等待 B/D 的 ABI 联合确认、C 的 range/错误协议确认和 E1 独立验证，状态为 BLOCKED。远端 CI 暂未运行。

[候选检查表](G0_CANDIDATE.md) · [运行证据](evidence/P03.txt)

## P04 组长独立验收

受测候选 `040cfe98c2e74cd0a741354e2b1a16cd3b5ec7bb`。干净工作树的上游、安装构建、串行运行、fixture、公共 ABI、CLI/schema 和本机 CI 对应步骤复核通过。**G0 CANDIDATE / BLOCKED**，待 E1 独立差分、B/D 联合 ABI 与 C 接口回执。GitHub Actions 托管运行是 NOT_RUN。 [验收矩阵与开工条件](../../gates/G0.md) · [P04 日志](evidence/P04.txt)

## P04.5 五人成果接收及 G0 复验

从 A 的候选建立独立集成工作树，接入 E1 并复跑 G0。两套独立差分、B/D ABI、C 运行时接口和项目回归通过。正式 G0 等待含 E1 的候选在托管 CI 上通过与组长签认。B/C/D 后续生产接入及原有 P05/P06 工作树在接收审计中登记。 [G0 当前状态](../../gates/G0.md) · [接收审计](../../gates/P04.5.md)

## P05 增量订单堆恢复

**MODULE_PASS**。从本地 P04.5 `835de4755b253a63b709b7a4cc446141a2ca8f46` 接回原 P05 `29042c469e74c4391f128ff88b94e5a138633878`，集成工作树为 `codex/p05-heap-integration`。受测源码 `3effd9afd4ae9887adb398086e13ad885fadd463`，契约 `coreorder-r4-v1`。

| 交付 | 验证 |
| --- | --- |
| `py-seq/upstream`、`py-seq/incremental` | 默认走原版 `Market`，增量仅将暂取订单逐项压回剩余合法堆。适配保留 E1 的只读观察接口。 |
| 双侧尺寸诊断与比较计数 | 默认关闭，各自可以独立启用。smoke 的 12 次恢复逐行满足 `n=h+k`，恢复全建堆 24 次变为 0 次，逐项压入为 52 次。 |
| 完整语义与边界 | A 侧 18 对、E 采集器 15 对 C01 代表比较以及 9 项定向边界通过。项目 80 项、上游选测 35 项、根 CTest 2 项和两套 E1 CLI 通过。 |
| 阶段边界 | 正式 G1-heap 签认待后续阶段，正式性能及原生集成为 `NOT_RUN`。 |

cherry-pick 在 `runner.py` 与 `STATUS.md` 出现两处冲突，已接合市场注册与观察钩子，保留 P04.5 历史记录。首次联合测试复现 PAMS wheel 与 vendor 导入冲突，pytest 进程统一走固定 vendor 后复验通过，CLI 子进程继续使用固定版本的安装包。 [方法与复现](HEAP_METHOD.md) · [真实日志](evidence/P05-integration.txt)

## P06 G1-heap 独立验收

P05 `2db0c2b9bed127b72119b83c6bf23293d5e5ee58` 的本地技术验收 **PASS**。原版对照通过 8 对包内模拟、15 对 C01 代表运行、7 类包内边界和连续新单。独立调用计数与生产 CLI 双侧诊断逐行一致，E 验证器 38 对复跑与旧结果逐案一致。正式 G1-heap 等待共同 G0 SHA 与 E 的审阅回执。 [门禁矩阵](../../gates/G1-heap.md) · [实跑日志](../../gates/evidence/P06.txt)

## P07 原生串行最小闭环

本地 **PASS**。以 P06 `74af43d` 为输入，在新分支 `codex/p07-native-serial` 接收 B 的真实串行核与 D 的 live packing。两套完整市场均通过未修改 PAMS 的 E 差分，项目回归 84/84。范围为 `native-serial/aos/upstream`。正式 G1-native 仍待相应验收和 G0 共同基线，生产多核与正式性能为 `NOT_RUN`。受测源码为 `da29dd6d4d80ffd1afebb059941a27e790a10070`。 [接口与复现](INTEGRATION.md) · [真实日志](evidence/P07.txt)

## P08 G1-native 独立验收

生产串行路径的两套完整市场精确差分和 10,181 个有效数值样本通过。**G1-native BLOCKED**，真实 CLI 复现第 1 行打包错误遮蔽第 0 行数值错误。首差、最小配置及 A/D 接口责任已登记。正式 G0 和 G1-heap 签认待完成，**完整 G1 BLOCKED**。 [门禁矩阵](../../gates/G1-native.md) · [执行日志](../../gates/evidence/P08.txt)

## P09 五后端全链路集成

本地 G2 候选 `92f8bbf08da514dcb24e27b6a815d3947c352798` 的 27 次完整市场差分通过。能力覆盖五种后端、两种堆恢复、AoS/SoA 及 Taskflow workers 1/2/4。P08 最早失败行反例和有效前缀对照共 8 项通过，项目测试 92/92。正式签认、托管 CI 和正式实验待对应阶段。 [P09 能力表与日志](INTEGRATION.md)

## P10 G2 系统验收

候选 `92f8bbf08da514dcb24e27b6a815d3947c352798` 的 56 次完整仿真与独立原版 PAMS 精确一致。**正式 G2 BLOCKED**，A/E 回执在配置身份和量测来源字段尚不兼容，现有共同 G0/G1 与正式签认未完成。真实可用范围与首次分歧已归档。 [G2 验收报告](../../gates/G2.md) · [原始记录摘录](../../gates/evidence/P10.txt)

## P11 堆机制诊断与 pilot

完成 Mac arm64 本地预实验，seed 11/29，五种负载全部保留。26 次低开销仿真与 26 次金融事件验证均完成，双侧堆记录 30,380 条。两个 30 秒计数超时留档，并在相同配置下以 60 秒诊断上限完成。原版恢复工作量和增量后的残余阶段均有独立证据。硬件 PMU、目标 x86、正式 H01/E05 和 G3 均未执行。 [诊断与冻结建议](RESULTS.md)

## P12 G3 冻结审查

R4 候选计划、区组、预算和准入条件已形成带 SHA-256 的文件。Mac 最小 raw 到图表链路通过，正式 E 回执拒绝已复现。G3 为 **BLOCKED**，目标主机 V01、E4 正式工具和签认仍未完成。正式运行授权为空。 [G3 报告](../../gates/G3.md)

## P13 正式堆机制证据审查

正式 H01/E05 仍受 G3 阻断，已接收正式 raw 和新增正式运行均为 0。重放现有 P11 汇总链路，核对 30,380 条双侧堆观测、六组同序金融事件与终态/RNG，交付标明 pilot 的机制图、数据与论文证据映射。 [结果与证据](RESULTS.md#p13-正式堆机制证据审查) · [raw 索引](evidence/P13/INDEX.md)

## P14 论文、答辩和可复现候选

本地独立克隆 `1027ee892f77963fbebc72839f322157be2821f8` 完成递归固定上游、Release 构建、92 项 pytest、2 项 CTest、许可核对和 E1 smoke。两市场 seed 42 的四条候选路径通过 E 的独立结构差分。论文、双页答辩与九题问答已交付本地候选。目标第二台物理设备和正式 H01/E05 均未运行，完整 FINAL 待核准。 [实跑与复现](p14/REPRODUCE.md) · 统稿与发布文档
