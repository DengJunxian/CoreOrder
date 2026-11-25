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
