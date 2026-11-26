# R5A 正式采集准入与覆盖报告

**2026-11-26（上海时间） · G3 BLOCKED · 正式原始运行 0 条**

受检候选身份为 `8113c98d7c108b8fd33dd86d35c7c63e890cf6f05fd731ded36551c26ce0219c`。候选锁的 G0/G1/G2/G3 均为 `BLOCKED`，没有生效锁摘要、正式源码登记或运行授权。A 和 E 的锁摘要签认字段都为空。组长先前批准的研究范围和候选清单已在 R4B 归档。本次 GitHub 查询看到旧 G0 草稿 PR，审查和讨论均为空。R5A 的准入函数对 timing 与 E05 均返回 0 条可运行记录。

[候选锁](../../configs/experiments/r4b/protocol_lock.json) · [GitHub PR #1](https://github.com/DengJunxian/CoreOrder/pull/1) · [查询证据](evidence/R5A/github-review.json)

## 目标机复核

- 华硕 x86 的干净受测提交仍为 `58ec5764c21833142c50abacd9e2302404ffdb06`。实际加载的扩展 SHA-256 为 `a9d294e6bac9098bb486d1ba3e728a0fa9f974eb858ad107fde858b86e16fc5e`。三个上游、依赖环境、编译器和 workload 摘要与封存验证身份一致。
- 只读重算 V01 原始文件的封存哈希，145 条验证均通过，其中生产候选回执 125 条、独立参考 20 条。493 条候选计时记录及诊断的条件与输入证明均能核对到对应证据。
- 检查时有线供电在线，Windows 电源计划为 Silent，WSL 1 分钟负载为 0.49，目标卷可用容量约 678 GiB。CoreOrder 主机锁可取得，无遗留运行租约，来宾和 Windows 的进程筛查均未观察到匹配的性能测试。
- ACPI 热区一次采样为 353 K（约 80°C），报告限频原因为 0。来宾显示 1996.203 MHz、Windows CIM 显示 2000 MHz。物理核心有效频率、CPU 封装温度和持续采集的热稳定性仍需在实际运行窗口检查。主机日志保留了初次 affinity 查询的参数错误及复查所得掩码。

[只读准入与 V01 复核](evidence/R5A/x86-admission.json) · [主机采样](evidence/R5A/host-snapshot.log) · [候选文件校验](evidence/R5A/candidate-checksums.log)

## 正式实验覆盖

| 实验 | 候选记录数 | 其中预热 | 有效 | 失败 | 超时 | 未运行 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| H01 | 102 | 12 | 0 | 0 | 0 | 102 |
| E01 | 85 | 10 | 0 | 0 | 0 | 85 |
| E02 | 170 | 20 | 0 | 0 | 0 | 170 |
| E03 | 136 | 16 | 0 | 0 | 0 | 136 |
| E05 | 76 | 12 | 0 | 0 | 0 | 76 |
| **合计** | **569** | **70** | **0** | **0** | **0** | **569** |

E05 计划含 4 条 profile、24 条 PMU、48 条 replay。正式数据缺口来自阶段门禁停止。R4A/R4B 的 pilot、校准和验证仍保留各自作用域。

下一次正式采集的输入是包含共同门禁和同版本独立签认的生效 G3 锁，以及明确授权的运行清单。启动时复查同机身份、供电、负载及热状态，并沿用现有封存 V01 的原始目录。

[覆盖台账](evidence/R5A/formal-coverage.json) · [R4B V01 回执索引](evidence/R4B/v01-index.json) · [准入复核脚本](evidence/R5A/preflight-x86.py)
