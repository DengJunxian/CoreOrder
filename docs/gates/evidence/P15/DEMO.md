# FINAL 实际复现与 Demo

## 本机干净克隆

复验在 Apple M5、macOS 27 ARM64、CPython 3.12.13 与 Apple Clang 21 上进行。从本地候选 `codex/p14-a-paper-repro` 作 `git clone --no-local`，受测提交为 `66630a8a9d803c7bb6563bd24d70d276d19fd8ef`。随后从真实远端获取三个固定上游，安装锁定 wheel，执行 Release 构建及测试。实际全链路退出 0，CTest 2/2，pytest 92 passed、39 warnings，E1 smoke 输出事件、逐步状态与完整末态 RNG 通过。扩展 SHA-256 为 `6063e31c146abe0d189b1f815cc4e22df556d09153755cc6017640f8d6228983`。 [配置、步骤和入口](../../../roles/A/p14/REPRODUCE.md) · [机器可读回执](reproduction.json)

完整命令以 `bash -x` 保存。本工作树的本地原始目录是 `results/acceptance/final/p15/`，其中 `rebuild.sh`、`rebuild.log`、`rebuild.exit`、`environment.json` 与 `smoke/` 构成 fresh-clone 证据。原始环境日志含本机路径，应留内部归档。非模块作者的独立回执尚未取得，目前身份为 P15 本机复验。

## 现场执行

在已建好的候选根目录运行下列命令。新路径是每次单独的输出目录。

```sh
bash docs/gates/evidence/P15/demo.sh results/demo-live
```

短市场为 `configs/workloads/native-serial-normal.json`，seed 为 42。脚本先调用 E1 smoke，再以原 PAMS 单独采集参考。候选依次覆盖 py-seq/upstream、py-seq/incremental、native-serial/AoS/incremental、native-parallel/SoA/incremental（2、1、4 workers）。原生并行固定 static、grain 2。18 个候选运行全部与参考的 `events`、`steps`、`initial`、`final`、`rng` 精确匹配。各试次都产生 184 条参考事件，包括 **89 条订单、28 次成交、25 次到期**；各语义摘要一致。

| 本机实跑 | 完整演示墙钟 | 退出码 | 结构差分 |
| --- | ---: | ---: | --- |
| 1 | 13.26 s | 0 | 6/6 |
| 2 | 14.02 s | 0 | 6/6 |
| 3 | 11.16 s | 0 | 6/6 |

墙钟涵盖 smoke、oracle 和六次比较流程，用于安排课堂操作。所有原始命令与时间分别保存于 `demo-{1,2,3}.log`，对应的退出码文件、目录内 manifest/配置哈希/比较和完整轨迹可核。演示记录仍被 E 的正式 gate 和 records 拒绝，正式统计不使用这些时间。 [18 条回执及状态](reproduction.json)

现场按顺序显示源码与配置身份、运行小市场、对照摘要与 worker 数，再打开历史 Apple M5 堆计数图。图表投屏应保留 P11、seed 11/29 和诊断标签。关于负结果，说明相同增量恢复基线下 W2-H 与 W3-START 的原生串行未进一步降时，W4 两个 seed 方向不一；保留仪器化和正式实验边界。 [历史实测及脚本](../../../roles/A/evidence/P13/INDEX.md)

如需展示负对照，原 E 的 `tests/differential/fault_demo.py` 提供故意扰动示例。故意扰动与三次上述正常运行分开，说明它的目的在于证明比较器能定位错误。 [故障样例](../../../../tests/differential/fault_demo.py)

## 离线应急

第三次实跑的未修改 PAMS 参考和四 worker 原生 SoA 候选已复制至 `results/acceptance/final/p15/offline/`。P15 在 macOS `sandbox-exec` 拒绝网络的进程内实际重放比较，退出 0，五个结构范围均通过。流程只需要已建环境与两份轨迹。在运行主机不可用时，现场按留存的结果表与该录存轨迹解释，同屏标注 **2026-11-26 的历史功能证据**。

```sh
.venv/bin/python -m validation compare \
  --reference /path/to/offline/reference.json.gz \
  --candidate /path/to/offline/candidate.json.gz
```

对照、两个源文件的 SHA 和运行身份见回执。P12 的诊断图和 P13 的 P11 机制图也已从 raw 复算。 [离线证据哈希](reproduction.json) · [图表重建回执](figure-audit.json)

## CLI 边界实测

`validate --suite g1`、`g3`、`final` 和 `run --unsupported-policy upstream` 均退出 2。可用的验证 suite 为 smoke、g0、g2。E 的采集与开发诊断模块 present，`experiments.run` 和 `analysis.report` 不存在。P15 保存了 `cli-*.txt` 的实际错误文本。
