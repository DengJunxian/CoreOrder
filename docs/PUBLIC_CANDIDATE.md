# CoreOrder 公开历史候选

此页记录 GitHub 上的 P15 快照。后续本地 R8 候选的技术验证、正式准入、论文和归档见 [FINAL 审计](gates/FINAL.md)。

公开分支 `codex/research-candidate` 提供已集成实现、依赖锁、对照脚本、论文与答辩素材、pilot 图和已完成的审计。生产源码与通过 P15 本机复验的候选一致。当前状态为 **FINAL BLOCKED**，正式实验的授权为空。 [验收矩阵](gates/FINAL.md) · [本机运行回执](gates/evidence/P15/reproduction.json) · [本分支 CI](https://github.com/DengJunxian/CoreOrder/actions/workflows/foundation.yml?query=branch%3Acodex%2Fresearch-candidate)

## 已取得的证据

Apple M5 干净克隆通过 92 项 pytest、2 项 CTest 和 E1 smoke。P10 的五后端技术矩阵与固定原版 PAMS 精确比较 56/56 通过。P15 的三次真实 Demo 共 18 条受测路径逐事件、逐步状态和 RNG 一致，另有本机禁网的离线重放。P11 的恢复比较次数和阶段剖析均标为 pilot，图表附制图数据。 [复现命令](roles/A/p14/REPRODUCE.md) · [Demo](gates/evidence/P15/DEMO.md) · [已实测图表](roles/A/evidence/P13/figures/heap-mechanism-pilot.pdf)

## 当前阻断

1. E gate 的 `input_hash` 身份口径与已产出的 manifest 不一致。E records 还拒绝 `setup_s` 的量测来源，且缺 `validation_run_id`。技术结构一致与正式资格分别记录。 [最小反例](gates/G2.md)
2. G3 候选尚未生效，V01 合格回执 0/140。目标 x86 与另一位非模块作者的正式复现未取得，H01、E05、PMU 和统计区间仍未测。相关账目继续使用 `BLOCKED` 或 `NOT_RUN`。 [冻结记录](gates/G3.md)
3. 自动整 run fallback 参数尚缺。当前原生路径接受已测精确 FCNAgent 与普通市场，不支持类型显式失败。团队统稿和合并课件待齐。 [最终风险清单](gates/evidence/P15/RELEASE.md)

## 来源、脱敏与复现

分支从已公开的 G0 候选提交 `f867a4fb07c928f459fa8b6d3e84a95ee88b1742` 接收本地 P15 树的公开快照。本机归档保留原 P15 提交 `f5a223b4eb93c0d60fa34a0fc814af79f5e0e924`、各阶段历史和原始凭据。生产身份对应 `92f8bbf08da514dcb24e27b6a815d3947c352798` 的实际生产文件，当前 GitHub 提交用于公开复现。B/C/D/E 的原始公开分支、接收映射和许可证见审计。

路径及宿主标识在公开诊断文本中替换为占位符。公开版 G3 的本机诊断附件与候选锁封套重算校验值，正式计划、负载、种子及正式锁状态保持原值。归档索引中的 `$COREORDER_ARCHIVES` 和 `$COREORDER_LEADER_PACK` 指持有人另存的原证据和组长包。公开分支提供聚合数据、图、脚本和验证回执。大体量原始证据、本机环境、构建缓存、可执行扩展和本地未提交成果保留在各自归档处。 [五人贡献与原分支](gates/evidence/P15/CONTRIBUTIONS.md) · [第三方来源与许可](../THIRD_PARTY_NOTICES.md)

```sh
git clone --branch codex/research-candidate --recurse-submodules \
  https://github.com/DengJunxian/CoreOrder.git CoreOrder-research
cd CoreOrder-research
git rev-parse HEAD
git submodule status --recursive
```
