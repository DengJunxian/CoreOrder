# R2A 正式计时路径 · 本机开发验收

实施基线是远端研究候选 `8f25a381f08ea9c398b6835c64ea470918819451`。测试时的源码是干净提交 `c3a0c527b9c29833b6a8cbb98566164e963b003a`。Release 扩展 SHA-256 为 `526ab0da9438569b3476ec540ae300f69f3a0bcd6e1e9b9b23c5976556e880d6`。本机 Apple M5、macOS 27.0 arm64、CPython 3.12.13、Apple Clang 21，使用锁定的 PAMS、Taskflow 和 pybind11。编译使用 `-O3 -fno-fast-math -ffp-contract=off`。 [运行契约](../../../CONTRACT.md) · [结构化回执索引](verification.json)

| 检查 | 状态 | 证据 |
| --- | --- | --- |
| Release 构建、CTest、pytest、E1 smoke | PASS | 各命令退出 0。CTest 2/2、pytest 112/112，E1 的事件、逐步状态和完整 RNG 均通过。 |
| `validation` 与 `timing` | PASS | 同一两市场配置、seed 42，覆盖五种后端、两种恢复、原生 AoS/SoA，共 14 对。两种模式的终态与完整 RNG 文件逐字节一致，核对了实际 runner、执行器、绑定及二进制。14 次 `validation` 的 E 独立结构差分均通过。 |
| 业务计数与观察边界 | PASS | 14 对均为 89 单、28 笔成交、25 次到期、0 次撤单、18 个市场步。原生为 35 次普通代理调用、57 个实际决策行、114 次 Gaussian API 调用。非零撤单另由真实簿边界测试覆盖。探针确认计时运行期间无逐步快照和剖析，终态与完整 RNG 在仿真后各生成一次。 |
| 阶段和函数剖析 | PASS | AoS 和 SoA 各记录 15 个原生批次的三个阶段，均检出处理订单及恢复阶段。独立 cProfile 产物用 `pstats` 读取并检查了真实订单处理调用。 |
| 故障退出与记录 | PASS | 禁用的组合退出 2。实测 spawn 限时 2 秒后，工作子进程退出 −9，保留 `TIMEOUT`、右删失与原始回执。 |
| Apple M5 的 `pmu` 调用 | UNSUPPORTED | 实际退出 2，工作量与硬件计数未采集。解析测试覆盖不可用事件。 |
| 目标 x86 PMU、V01、正式实验矩阵 | NOT_RUN / BLOCKED | 目标主机未测试，G3 候选继续为 `runnable=false`。 |

### 轻量计数开销

使用锁定 PAMS 的原始 CI2002 样例，seed 11。P11 的原版 `Logger` 与 R2A 计数器使用相同 runner 和金融配置。每组 8 对，交替先后顺序。每次执行完整仿真，计时后验证终态和 RNG 一致。表中比值为启用计数除以原版 Logger；低于 1 表示该次启用计数的仿真更短。该小规模敏感性测试只用于核查本机观测开销。

| 后端 / 恢复方式 | 中位数 | 观察范围 |
| --- | ---: | ---: |
| py-seq / upstream | 1.039 | 0.934–1.093 |
| py-seq / incremental | 0.994 | 0.806–1.043 |
| native-parallel / SoA / 2 workers / incremental | 0.994 | 0.922–1.058 |

原始运行在工作树的 `results/r2a/verification/`，其中 `pytest-runs/` 保留完整 mode 对照产物，`logger/logger-probe.json` 保留 24 对计时。初次剖析发现 CPython 把 pybind11 绑定方法的底层函数传给 `c_call`。初次聚焦测试还发现 pytest 的路径设置与安装版 PAMS 身份核验不同。修正记录分别位于 `results/r2a/bootstrap/profile-smoke/`、`profile-binding-probe/` 和 `pytest-focused/`。后续测试使用干净提交，安装版 PAMS 通过入口自身的身份核验。 [探针源码](logger_probe.py) · [命令、退出码及产物 SHA-256](verification.json)
