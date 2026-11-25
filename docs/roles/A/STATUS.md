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
