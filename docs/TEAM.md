# CoreOrder 目录所有权与 PR 审查

| 角色 | 维护目录和接口 | 主要审查人 |
| --- | --- | --- |
| A | `src/coreorder/` 中 runner、config、CLI、market/snapshot、公共 dtype 与 schema 接入，`include/coreorder/contracts.hpp`、`schemas/`、`fixtures/`、`configs/workloads/`、`tests/platform/`、`tests/heap/`、根构建、依赖锁、vendor 和 CI | 平台语义由 E 审，公共接口由相关消费者 B/C/D/E 确认 |
| B | `native/fcn/`、`native/bindings/`、`tests/native/`，单一 FCN scalar/range 核及绑定 | A、E |
| C | `native/runtime/`、`tests/runtime/`，持久执行器、range 划分及错误 | B、E |
| D | `src/coreorder/packing.py`、`native/layout/`、`tests/layout/`、`benchmarks/layout/`，AoS/SoA views 和 packing | B、E |
| E | `validation/`、`tests/differential/`、`experiments/`、`configs/experiments/`、`analysis/`、`docs/gates/`、`results/`，独立验证和实验 | A 与相关模块负责人 |

各自维护 `docs/roles/<ROLE>/`。每个阶段基于最新共同基线建立短分支，PR 指向 `main`，记录范围、来源与许可证、真实命令与退出码、语义影响、验证证据和待交接事项。审查人阅读实际 diff 与日志并复跑关键检查，涉及公共变更先记录接口提议，经受影响的消费者确认后由 A 合入公共文件。PR 通过必需 CI 和审查后，由组长按授权合入，门记录实际验收 SHA。当前工程交付从 `main` 获取。

候选 CI 检查递归子模块、固定依赖、项目 pytest、C++17 CTest 与指定上游 pytest 子集。CI 的 A 侧检查与 E 的独立整机验收各自保留实际运行证据。
