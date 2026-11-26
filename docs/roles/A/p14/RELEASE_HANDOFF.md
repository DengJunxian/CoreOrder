# 交 E 统稿与组长候选审查

论文稿按 E 的 System and Semantics、Methodology、Evaluation、Discussion 组织。课程演示可单独插入 A 的两页。古典堆原理、PAMS 平台、Taskflow 和各队友的贡献已分别署明。P14 是成员 A 的文档候选，完整项目 FINAL 待验。 [论文初稿](PAPER_DRAFT.md) · [两页 PPTX](A-defense.pptx) · [两页 PDF](A-defense.pdf) · [讲稿及九题问答](DEFENSE.md)

## 统稿证据对照

| Claim | 可用陈述 | 源码、运行和图 | 审查状态 |
| --- | --- | --- | --- |
| C1 · 平台语义 | 原版市场、账户与有序提交沿用 PAMS，受测候选与固定原版的金融轨迹精确匹配 | [原版 Runner](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/runners/sequential.py#L561-L746) · [G2 本地 56 对](../../../gates/G2.md) · [P14 四路复现](reproduction-receipt.json) | 本地实测，共同 G2 与正式 V01 待签 |
| C2 · 恢复工作量 | 保持原配对与统一价，以合法余堆恢复同一对象，pilot 六对恢复比较更少。W2-H、seed 11 的两侧合计为 8,245,535 和 92,206 | [恢复源码](../../../../src/coreorder/market_adapter.py) · [P06 定向证据](../../../gates/G1-heap.md) · [pilot raw、逐侧 CSV 和重算命令](../evidence/P13/INDEX.md) | 机制图作为 pilot，H01 正式结果待采 |
| C1 · 可并行边界 | 对精确 FCN 按剩余名额切前缀，在 Python 保持访问和 RNG，独占槽汇合后仍按原位置重建 | [批次代码](../../../../src/coreorder/native_serial.py) · [集成说明](../INTEGRATION.md) · [执行图](figures/execution-dataflow.pdf) | 可写方法，跨 ISA 及自定义类型暂无验证 |
| C6 · 瓶颈迁移 | Apple M5 的 W1-H、seed 11 从恢复热点迁移到明显的抽样工作，比较次数与分段时间分别有来源 | [P11 剖析和仪器化边界](../RESULTS.md) · [原始归档](../evidence/P13/INDEX.md) | pilot，正式 E05 与 PMU 待采 |
| C7 · 跨设备复现 | Apple M5 的干净克隆通过 smoke 及两市场语义对照 | [命令与机器回执](REPRODUCE.md) | 本机 PASS，E 的第二台物理设备及正式配置未运行 |

## 图与版本

- 系统执行数据流为矢量 [PDF](figures/execution-dataflow.pdf)，配套 [DOT](figures/execution-dataflow.dot) 与 [PNG](figures/execution-dataflow.png) 可复用。实线为执行，虚线为提交后的观测和参考，两侧恢复在上游市场调用内。通过 `neato -n2 -Tpdf execution-dataflow.dot -o execution-dataflow.pdf` 重建。
- 增量恢复 [机制示意](figures/heap-restore.pdf) 用七个优先级序号展示两种不同堆数组和同一后续出堆序列，数组已用 CPython `heapq` 核对。序号用于讲解，实验观测来自下列 pilot 图。 [DOT](figures/heap-restore.dot) · [PNG](figures/heap-restore.png)
- 堆机制与结果图复用 P13 从 P11 raw 再生的 [PDF](../evidence/P13/figures/heap-mechanism-pilot.pdf) 和 [CSV](../evidence/P13/figures/heap-mechanism-pilot.csv)。图中标注机器、seed、计数边界和 pilot 用途。完整 H01、E05 条件及缺测值见 [正式状态表](../evidence/P13/formal-status.json)。
- 两页答辩 PPTX 中的文字为原生可编辑文本，图可独立替换。使用 `python-pptx` 运行 `python build_defense.py` 再生 PPTX，源图保持仓库相对路径。字体采用 Noto Sans CJK SC。PDF 基于实际导出的 PPTX。
- 生产候选 SHA 为 `92f8bbf08da514dcb24e27b6a815d3947c352798`，本机 P14 功能复现从 `1027ee892f77963fbebc72839f322157be2821f8` 创建干净克隆。文档候选 SHA 读取 P14 的 Git HEAD。正式实验 SHA 由 G3 生效后写入。

## 发布候选回执

| 检查 | 当前回执 |
| --- | --- |
| 源与许可证 | 固定 PAMS EPL-1.0、Taskflow MIT、pybind11 BSD-3-Clause。三份留存许可逐字节比对通过，PAMS 衍生恢复代码有 SPDX 和来源 SHA。 |
| 构建与功能 | 本机干净 clone、92 项 pytest、2 项 CTest、E1 smoke、4 条代表路径结构差分通过。 |
| 归档边界 | Git bundle 保留候选提交历史和 gitlink，仍需从上游获取 submodule。大体积 raw 留独立归档，用 SHA-256、配置和包含失败记录的完整清单关联。发布包排除本地二进制、构建缓存、设备私密路径和凭证。 |
| 适用性与隐私 | 候选历史中仍有包含本机绝对路径的旧文档，包括 P12/P13 的诊断产物。发布前先审查路径和宿主标识，公开数据包保留经检查的结果和可复算索引，原始本地证据单独保存。当前文档改动使用相对路径。 |
| FINAL 和远程授权 | 共同 G2/G3、正式数据和第二设备回执仍缺。组长完成 FINAL 与公开审计后确定 tag，候选命名可用 `coreorder-r4-course-rc1`，实际 tag 绑定审定 SHA。GitHub Release 由用户明确授权后执行。 |

发布说明草案可表述为“在固定版本 PAMS 上实现了语义保持的增量堆恢复和确定性 FCN 批次。包含受支持配置的独立验证、Apple M5 pilot 机制记录与可重建材料。设备及正式测量范围以逐项回执为准。”在 FINAL 前，公开版本仍保留 G3 和跨设备复现的未完成状态。
