# 五人真实交付与接收审计

范围为 GitHub 当次实际分支、各自提交中的交接与本机已有工作树。PR #1 仍为旧 A Draft。A 的原 G0 分支属于候选祖先，B/C/D/E 均按模块路径选择接收，原分支的完整历史在原 refs 中可查。合并作者和本地审计人由证据记录，不以合并者替代原作者。

| 人员 / Git 作者 | 远端实查 HEAD / 来源 | 可核贡献和接收证据 | 课件与终稿 |
| --- | --- | --- | --- |
| A · Deng Junxian | `f867a4fb07c928f459fa8b6d3e84a95ee88b1742`，与本地 P05–P15 链 | 锁定平台、公共 ABI/schema、候选 CLI、合法余堆适配 `614dacf`、安全批次 `da29dd6`、整机组合 `92f8bbf`。P06 对照与 P11 原始计数分别支持等价和恢复工作量。 [方法与结果](../../../roles/A/PAPER_NOTES.md) | P14 实际两页 PPTX/PDF、九题、论文和复现收录。 |
| B · YASEILANEI | `f8d2be9f1391ac5e430112665efaff7bb844c507`，实现 `0e5bf62` | FCN 唯一标量公式、direct loop 和 pybind11。候选 `native/fcn/evaluate.cpp`、`native/bindings/fcn_binding.cpp` blob 与 B HEAD 一致。接收 `4667b96` 保留 B 作者。原 FCN 数值复验、ABI 和错误路径证据可查；std::async 只在 B 测试。 [B 原交付](https://github.com/DengJunxian/CoreOrder/tree/f8d2be9f1391ac5e430112665efaff7bb844c507/docs/roles/B) | 方法与两页底稿，B4/B5 正式结果、定稿课件与实讲未见。 |
| C · pengdeyuan06 | `5ad1ecb78272ff2564075cf01a90df252ae7e7ba`，实现 `e615358`、测试 `cfe9877` | 持久 Taskflow、半开区间、独占输出、汇合与确定性异常。候选 executor 的 .cpp/.hpp 两个 blob 与 C HEAD 一致。接收提交 `b3e8560` 由 A 作集成并标明来源。C 自有复用/异常测试和 P10 真实模块覆盖分别归档，数值 fixture 未进入生产。 [C 原交付](https://github.com/DengJunxian/CoreOrder/tree/5ad1ecb78272ff2564075cf01a90df252ae7e7ba/docs/C) | 论文段落与问答初稿。C4/C5 自报 NOT_RUN，缺最终两页和端到端曲线。 |
| D · swel | `decccbf55955e3fbeb4bbe5266eb0c2b043b3f75`，实现 `a56e485`、`3ef2298` | AoS/SoA、live packing 和 buffer 生命周期。候选 `src/coreorder/packing.py` blob 与 D HEAD 一致。接收 `8b63c8c` 保留 D 作者。ABI 对齐及事件刷新各有独立证据。实际 Python 采样由 A 按序提供，D 不拥有原生计算公式。 [D 原交付](https://github.com/DengJunxian/CoreOrder/tree/decccbf55955e3fbeb4bbe5266eb0c2b043b3f75/docs/roles/D) | 论文方法和两页底稿，D4/D5 与正式 PMU 未见。 |
| E · cheng123456916 | `b05d5555fa5cc756a91ab61c644e797ca227c26f`，实现 `533ab87` | 固定 PAMS 独立参考、按序资料、精确差分、首差回放及开发计时工具。接收 `5eb8690` 保留 E 作者。集成后 A 只扩展了差分的初态检查和结构首差、以及串行参考的配置处理，金融参考仍用原 PAMS。E 的独立错误样本和 P15 真实 gate 拒绝均保留。 [E 原交付](https://github.com/DengJunxian/CoreOrder/tree/b05d5555fa5cc756a91ab61c644e797ca227c26f/docs/roles/E) | E1–E3 验证方法及两页底稿。E4 正式工具、E5 总稿/团队整套 PPT、第二位复现者回执未见。 |

B/C 基于 A 的 `f867a4f`，D/E 基于初始化 `e2492a4`。P15 复核源与候选 blob，并检查完整原分支可见的测试、状态和方法段落。E 的轻量分支说明原始 `CoreOrder_E1-E3.bundle` 单独交付，当前未取得。其缺失影响部分原始案例的完整核对，不撤销 P15 自己重新采集的本机证据。 [P04.5 选择性接收范围](../../P04.5.md) · [E 原证据索引](../../../roles/E/EVIDENCE_ARCHIVE.json)

## 课程汇报完整性

建议按公共材料的 15 分钟汇报和 3 分钟 Demo 设计审查。已有内容支持 A 讲平台、堆与次序，B 讲浮点、Gaussian 和 binding，C 讲持久池、独占槽和 barrier，D 讲 112B/16B ABI 和内存布局，E 讲独立参考、配对统计与证据界限。对应课程知识为数据结构与算法工作量、浮点/舍入、多核同步、局部性和可信测试。示例不依赖未经核对的课本章号。完整合并 PPT、总时长记录、B/C/D/E 终稿及跨角色交叉审查回执仍缺。三次本机 Demo 通过项独立保留。 [A 实际 PPTX](../../../roles/A/p14/A-defense.pptx) · [现场回执](DEMO.md)
