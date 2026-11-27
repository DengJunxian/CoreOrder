# R8 五人贡献与接收审计

原始 A 交付见 G0 分支和平台实施记录。B–E 的远端分支与 `main` 各自保留。分支头标识原交付范围，接收记录标识生产树的纳入方式。源码注明来源，集成作者与模块作者分别登记。

| 角色 | 原始可核贡献 | 原提交与接收 | 代表性结果 |
| --- | --- | --- | --- |
| A · Deng Junxian | 固定 PAMS、公共 ABI、增量堆恢复、安全 FCN 批次和整机集成。后续负责运行模式、实验执行与统计工具的生产接入及 x86 流式验收。 | `614dacf`、`da29dd6`、`92f8bbf`；R2A `c3a0c52`、R2B `dee54bb`、R4B `58ec576` | 堆恢复 W1-H seed 101，V01 upstream `4d4084b6033b4b5eb8ca82c3742dd275`，incremental `19fe7d05557c4fe0be3b162500a9c2d8`。 |
| B · YASEILANEI | 同一 FCN 标量公式、direct/range、绑定与精确浮点和异常回归。 | 原实现 `0e5bf62`，原分支 `f8d2be9`，接收 `4667b96` | W2-H direct AoS `6d10cadf6ca44b87b8e40221f4e24bea`。 |
| C · pengdeyuan06 | 持久 Taskflow 执行、半开区间、独占输出、汇合、确定性异常和重入回归。 | 原实现 `e615358`、`cfe9877`，原分支 `5ad1ecb`，接收 `b3e8560` | W3 seed 101 的三个并行 worker 点对同一独立参考通过。 |
| D · swel | AoS/SoA、live packing、布局缓冲与事件刷新。 | 原实现 `a56e485`、`3ef2298`，原分支 `decccbf`，接收 `8b63c8c` | W2-H direct 与 4-worker 的两布局各有 V01 回执。 |
| E · cheng123456916 | 原 PAMS 独立参考、有序观察、首差诊断、故障注入与独立记录协议。原始验证与实验设计由 E 交付，生产工具后续由 A 集成。 | 原实现 `533ab87`，原分支 `b05d555`，接收 `5eb8690` | W3 seed 101 独立参考 `07e25c0ca8ff4ed495db1e8f2d9639b5`。V01 共 20 条独立参考及 125 条生产候选。 |

[历史来源核对](../P15/CONTRIBUTIONS.md) · [R3 回归恢复来源](../R3/README.md) · [原始回执索引](../R4B/v01-index.json) · 完整论文补充材料

E 的完整历史 `CoreOrder_E1-E3.bundle` 由成员记录为另行交付。R8 搜索仓库对象、现有项目与下载目录、目标主机相关目录及 GitHub Release，未取得该 bundle。公开 E 分支及其清单仍可定位所缺历史。R4B 新的封存正确性和 R8 原始封存复验覆盖当前候选，历史 E1–E3 全量原始目录仍缺失。 [E 声明及预期 SHA-256](../../../roles/E/EVIDENCE_ARCHIVE.json)
