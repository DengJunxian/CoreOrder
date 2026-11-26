# CoreOrder FINAL 审计

**2026-11-26（上海时间） · FINAL BLOCKED · 本机功能复验通过 · 公开发布暂缓**

P15 审查了本地生产候选、五人最新可见交付、真实门禁与原始证据。Apple M5 上的干净克隆完成递归依赖获取、Release 构建、92 项 pytest、2 项 CTest 和 E1 smoke。三次同 seed Demo 共 18 条候选路径通过 E 的结构差分。E 的正式 gate 和 records 再次拒绝全部 18 条。本机能运行最小完整系统。正式 G0/G1/G2/G3、V01、目标 x86、第二位复现者与团队最终文稿仍缺交付。 [构建及逐条回执](evidence/P15/reproduction.json) · [P10 共同门禁](G2.md) · [P12 冻结](G3.md)

## 逐项验收矩阵

| 范围 | 判定 | 证据、缺口或责任 |
| --- | --- | --- |
| PAMS、许可证与锁定构建 | **PASS（本机）** | 三个 gitlink 干净，许可副本逐字节一致。P15 CPython 3.12.13、Apple Clang 21，实际加载原生扩展。 [构建回执](evidence/P15/reproduction.json) |
| 增量恢复与原版等价 | **PASS（本机受测范围）** | P06 23 对完整仿真与 8 个定向边界。P15 上游和增量均对未修改 PAMS 精确一致。撤单与到期仍由上游处理。 [堆门禁](G1-heap.md) |
| 五后端、两堆模式、AoS/SoA、原生串行与多核 | **PASS（本机受测范围）** | P10 56 对覆盖五后端及原生布局、workers 1/2/4 和静动态调度。P15 两市场演示复验串行 AoS 和并行 SoA，真实直接循环创建 0 个 executor，并行每 run 创建 1 个。 [本机矩阵](G2.md) · [演示回执](evidence/P15/reproduction.json) |
| 目标 x86/跨设备支持 | **NOT_RUN** | Apple M5 是已验证的代表设备。指定主机缺实际扩展、拓扑、环境和独立运行回执。跨 ISA/libm 位级等价未验。 [目标机锁字段](../../configs/experiments/protocol_lock.json) |
| 能力边界与 fallback | **FAIL（自动后备入口）** | `--unsupported-policy upstream` 实际退出 2。用户可在运行前明确选择 `py-seq`。本地已验证不支持类型报错、无扩展显式拒绝及异常批次停止。原生只涵盖普通 Market、精确 FCNAgent、已测 MarketMakerAgent HFT。收费模型的 E 完整编码仍缺。 [G2 能力边界](G2.md) |
| 正式 G0 | **BLOCKED** | E1 smoke 和本地公共基线证据存在。远端 Draft PR #1 仍是旧 A 快照，生产候选 SHA 的托管 CI 与共同签认缺失。 [G0](G0.md) |
| 正式 G1-heap | **BLOCKED** | 本地技术复验通过。绑定同一候选的共同 G0 和正式签认未齐。 [G1-heap](G1-heap.md) |
| 正式 G1-native | **BLOCKED** | P08 的两套有效市场精确一致。早期“最早坏行”问题已在后续整机候选复验通过。完整 G1 仍缺共同 G0、验收回执和签认。 [G1-native](G1-native.md) · [后续回归](G2.md) |
| G2 语义与工作量 | **PASS（技术对照）** | P10 56/56 和 22 条 tick 调整前订单对照，与原版 PAMS 逐事件及完整状态一致。P15 的 18 条也具有相同金融工作量，保留 89 订单、28 成交、25 到期。 [输入、环境哈希和运行 ID](evidence/P15/reproduction.json) |
| E 准入与正式 G2 | **FAIL / BLOCKED** | P15 用真实记录复验，18/18 在独立 gate 的 `input_hash` 失配，records 在 `setup_s` 来源字段拒绝；`validation_run_id` 为空。A/E 需修订并审查共同的回执身份、度量来源和关联格式。 [最小反例与责任](G2.md) |
| G3 和 V01 | **BLOCKED** | 候选字节、配对、种子和预算复校通过。`runnable=false`，正式授权为空，已接受 V01 为 0/140，正式 SHA 与锁生效哈希为空。 [冻结文件](../../configs/experiments/frozen.json) · [G3](G3.md) |
| 实验入口及统计链 | **FAIL（正式入口缺失）** | `experiments.capture`、`experiments.diagnostic` 和 E 独立验证可用。`experiments.run`、`analysis.report` 缺失。`validate` 接受 smoke/g0/g2，g1/g3/final 实跑均退出 2。 [现场及复现日志说明](evidence/P15/DEMO.md) |
| H01、E01/E02/E03/E05、正式 raw 与 PMU | **NOT_RUN** | 核查现有 CoreOrder 运行目录 882 份 manifest，0 份含合格的 `validation_run_id`。正式采集有效记录为 0。固定规划仍为五 seed × 三配对重复、seed 区组 bootstrap、保留超时和缺配对。无正式估计、区间或缓存证据。 [状态与原始索引](../roles/A/evidence/P13/INDEX.md) |
| 从 raw 重建核心图表 | **PASS（现有诊断）** | P12 三实际 run 的工作量链路、P13 的双侧堆 pilot 均从原始记录重建。五项图表文件逐字节一致，P11 的 30,380 条观测及 2 次超时保留。正式图表 **NOT_RUN**。 [重建回执](evidence/P15/figure-audit.json) |
| 干净克隆复现 | **PASS（P15 本机）** | 从本地候选分支作 `--no-local` 克隆，递归到原上游，记录命令和退出码，重新执行 smoke 和真实两市场对照。 [复现说明](evidence/P15/DEMO.md) |
| 非模块作者独立复现及正式配置 | **NOT_RUN / BLOCKED** | P15 同一物理设备的技术复验已经独立重新构建。尚无另一位非模块作者提交的实际回执，也无可放行的正式配置。E 和组长负责收取可复核的操作者、环境、命令和输出。 |
| 论文审计 | **PASS（现有方法和 pilot 素材） / BLOCKED（正式统稿）** | 已审 A 论文、B/C/D 模块草稿与 E 验证框架。完整团队课程论文和正式结果缺失。 [论断、数字与引用](evidence/P15/PAPER_AUDIT.md) |
| 课程 PPT、五人答辩素材 | **FAIL（完整交付）** | A 有实际两页 PPTX/PDF 及九题。B、D 有两页底稿，C 有题纲，E 有 E1–E3 两页底稿。缺团队完整汇报文件、B/C/D/E 定稿和全员彩排回执。 [五人审计](evidence/P15/CONTRIBUTIONS.md) |
| 现场 Demo 与离线应急 | **PASS（本机）** | 三次实际退出均 0，18 条结构对照一致，同时复验 workers 1/2/4。复制第三次真实轨迹并在网络拒绝的进程中离线比较，退出 0。 [操作入口和备用路径](evidence/P15/DEMO.md) |
| 贡献、隐私与发布 | **PASS（可追溯贡献、依赖来源） / BLOCKED（公开发布）** | 五人原分支和接收提交可核。旧历史含本机路径，原 E 证据包仍缺。当前代码与归档可内部审查。 [发布内容及路径审计](evidence/P15/RELEASE.md) |

## 版本与本轮改动

| 身份 | SHA 或实际状态 |
| --- | --- |
| 生产候选 | `92f8bbf08da514dcb24e27b6a815d3947c352798` |
| P15 fresh clone 受测提交 | `66630a8a9d803c7bb6563bd24d70d276d19fd8ef` |
| P11 pilot 的实际运行 checkout | `3c344f765c6ff288abad2faa6081c921f0ee0f36` |
| P12 协议、P13 审查与 P14 文档 | `fef940ec3d9c9ffbed0d7732fd9f8a8243b1b9bb`、`1027ee892f77963fbebc72839f322157be2821f8`、`66630a8a9d803c7bb6563bd24d70d276d19fd8ef` |
| 正式实验代码 SHA、实际正式扩展、正式锁 | **未签认，均为空** |
| FINAL 本地文档与发布候选 | `codex/p15-final-audit` 的提交及本地内部源码包，见随包校验清单。 |

本轮修订 README 的复现入口和功能范围说明，并加入现有 CLI 的演示调用、实测回执与审计记录。源代码、锁、schema、配置、计时边界、oracle 与过往日志均未修改。A/E 先完成回执修复及正式 G0–G2 签认，再在获准主机完成 V01 与 G3。任何受测生产条件变更均按 G3 既定规则重验重测。团队论文、课件与独立复现证据齐备后再审查公开发布。 [发布次序与风险](evidence/P15/RELEASE.md)
