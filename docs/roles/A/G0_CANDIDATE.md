# G0 候选检查表

P03 在 `a/01-foundation` 提供 A 侧候选。G0 状态 **BLOCKED**，等待消费者确认与 E1 独立验证。候选 SHA 以包含本检查表的提交为准。

| 验收项 | 实际状态 | 责任人与待交回证据 |
| --- | --- | --- |
| 固定上游与许可、Python 依赖 | PASS | A 已核对递归 gitlink 和未改上游、原许可；Python 3.12 安装及 `pip check` 通过。 |
| 原版 CI2002、`py-seq/upstream`、三类真实 fixtures | PASS（A） | P02 执行回执与 P03 fixture 生成记录。A 侧真实 run 的阶段状态可复核。 |
| 独立逐事件、逐步状态和最终 RNG 差分 | BLOCKED | 等待 [E1](P03_HANDOFF_E.md) 的独立采集、比较器、首差异记录和两套 CLI 回执。A 侧共享观察器的比较覆盖本机记录格式及调用链。 |
| 112/16 字节 ABI 与视图 | PASS（A） · BLOCKED（消费者） | A 已实测 C++17、NumPy、字段类型和偏移。等 [B](P03_HANDOFF_B.md)/[D](P03_HANDOFF_D.md) 用各自工具链共同确认。 |
| range、独占 slot、错误传播 | PASS（A 公共边界） · BLOCKED（消费者） | 公共头与区间边界已编译运行，等 [C](P03_HANDOFF_C.md) 的确认及最小生产调用和错误证据。 |
| 工作负载、运行记录 schema、非静默拒绝 | PASS（A） | pytest 实际校验 schema、真实数据和未知阶段后端拒绝。 |
| CI 与复现 | PASS（本机 CI 对应命令） · NOT_RUN（托管 CI） | workflow 已建立，实际托管运行在有授权的远端 PR 或分支出现后核查。 |
| 组长 G0 审核与共同冻结 | BLOCKED | 收齐 B/C/D/E 回执后，按 G0 验收规范对实际候选 SHA 执行独立审核。 |

[公共契约](../../CONTRACT.md) · [命令与退出码](evidence/P03.txt) · [A 状态](STATUS.md)
