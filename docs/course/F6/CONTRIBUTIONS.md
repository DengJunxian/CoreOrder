# 五人贡献与源码接收对应

答辩材料沿用成员 A–E 标签，组内确认后填写个人署名和作者顺序。原始研发对象、A 后续生产集成以及本轮自动化材料整理分别保留身份。

| 成员 | 原始研发 | 原始 Git 对象及接收 | 核验入口 |
| --- | --- | --- | --- |
| A | PAMS 平台选择、固定依赖和 ABI、增量恢复、安全批次与分层验收。后续接收 B–E 并接入生产、计时、执行器、统计入口及 x86 流式校验。 | `614dacf`、`da29dd6`、`92f8bbf`；后续 `c3a0c52`、`dee54bb`、`58ec576` | [平台和堆方法](../../roles/A/HEAP_METHOD.md) · [F4 正式效应](../../results/README.md) |
| B | FCN 标量求值、direct/range 接口、pybind11、严格浮点、输入验证及异常回归。 | `0e5bf62`；原分支头 `f8d2be9`；接收 `4667b96` | [原分支](https://github.com/DengJunxian/CoreOrder/tree/b/01-03-native) |
| C | 持久 Taskflow 包装、静态分块、并行异常汇合、独占区段、重入及确定性回归。 | `e615358`、`cfe9877`；原分支头 `5ad1ecb`；接收 `b3e8560` | [原分支](https://github.com/DengJunxian/CoreOrder/tree/c/01-03-runtime) · [真实粒度](../../gates/evidence/T05/analysis.json) |
| D | 同字段布局 ABI、AoS/SoA 缓冲和租用、实时 packing、事件刷新、边界诊断。 | `a56e485`、`3ef2298`；原分支头 `decccbf`；接收 `8b63c8c` | [原分支](https://github.com/DengJunxian/CoreOrder/tree/d/01-03-layout) · [布局剖析](../../results/README.md) |
| E | 原版 PAMS 独立 oracle、事件和状态采集、首差、注入测试、证据记录及实验契约；A 后续接入生产执行与目标机封存。 | `533ab87`；原分支头 `b05d555`；接收 `5eb8690` | [原分支](https://github.com/DengJunxian/CoreOrder/tree/e/03-github-delivery) · [验证规范](../../roles/E/VALIDATION_SPEC.md) |

E 的历史完整证据 bundle 原件仍缺。公开 E 源码和声明、当前目标封存以及 R8 和 T09 的实跑支持本文对应的现有证据。 [历史归档声明](../../roles/E/EVIDENCE_ARCHIVE.json) · [R8 接收审计](../../gates/evidence/R8/CONTRIBUTIONS.md)

课程口述分为五份，详细记录取得的正负结果。可编辑个人附页按 A–E 各两页，分别给出原始责任与实证。 [五人讲稿](DEFENSE.md) · [十页个人附页](CoreOrder-Contributions.pptx)
