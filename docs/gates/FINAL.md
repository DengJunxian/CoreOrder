# CoreOrder 最终工程与实证交付

2026-11-27（上海时间）。默认分支为最终工程快照。生产、构建、验证、数据和课程入口见 [README](../../README.md)。

| 范围 | 结果与证据 |
| --- | --- |
| 工程 | 固定 PAMS、Taskflow、pybind11。集成增量堆恢复、确定性原生批次、AoS/SoA、五种执行后端、独立 PAMS oracle 和测量工具。 [构建入口](../../README.md#build-and-test-the-pinned-system) |
| 正确性 | 华硕 C01 420/420、V01 145/145。485 条生产尝试与 80 条独立参考均通过。 [C01 索引](evidence/R4B/c01-index.json) · [V01 索引](evidence/R4B/v01-index.json) |
| 性能与机制 | 独立组长授权下 465 条计时、62 条预热、79 条 E05。375/375 个配对位置齐全，零失败和超时。专用 LLC 缺测。 [结果表和图](../results/README.md) |
| 课程答辩 | 19 页团队课件、10 页五人附页、五人讲稿和 42 问。华硕功能 Demo 六种后端配置全部对齐独立参考。 [课件](../course/F6/README.md) · [Demo](../course/F6/DEMO.md) |
| 门禁与人员复现 | 原 A/E 双人 G3 保持 BLOCKED。团队成员独立操作签认待完成。 [门禁](G3.md) · [复现](../course/F6/REPRODUCTION.md) |

华硕正式运行的生产提交为 `58ec5764c21833142c50abacd9e2302404ffdb06`，实际原生扩展 SHA-256 为 `a9d294e6bac9098bb486d1ba3e728a0fa9f974eb858ad107fde858b86e16fc5e`。本分支集成了其生产、构建、验证源码和后续通过资格检查的统计与 PMU 工具。详细依赖身份见 [UPSTREAM.lock.json](../../UPSTREAM.lock.json)，成员原始提交与集成映射见[贡献说明](../course/F6/CONTRIBUTIONS.md)。
