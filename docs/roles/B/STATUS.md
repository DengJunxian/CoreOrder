# B1 至 B3 阶段交付

**成员 B 独立研发 `MODULE_PASS`。生产联调 `INTEGRATION_PENDING`。正式全系统性能实验 `NOT_RUN`。**

## 公共基线

开发分支 `b/01-03-native` 从 `codex/g0-candidate@f867a4fb07c928f459fa8b6d3e84a95ee88b1742` 创建。契约 `coreorder-r4-v1`。使用候选的 C++ 头、NumPy dtype 和公开 FCN fixture。G0 的共同验收仍由组长负责。成员代码提交 SHA 可在 GitHub 分支或 `git log -1 --format=%H b/01-03-native` 读取。 [G0 候选 PR](https://github.com/DengJunxian/CoreOrder/pull/1)

## 完成清单

- B1 完成固定 PAMS 源码审计、许可核对、原包 10,000 用例探针复现和本机 ABI 检查。 [数值规则](NUMERIC_SPEC.md) · [原始探针输出](evidence/original-probe.json) · [B1 布局输出](evidence/abi.json)
- B2 实现 `native/fcn/evaluate.cpp` 的唯一标量公式和公共 `evaluate_range`。范围支持 0、1 与尾块，直接串行路径不创建 executor。复核公共 ABI 的 112/16 字节、8 字节对齐及全部字段偏移。 [模块代码](../../../native/fcn/evaluate.cpp)
- B3 交付 AoS/SoA 绑定、严格 dtype/shape/stride/字节序/对齐验证、owner 生命周期、GIL 与首个错误行报告。执行器接口支持每次 run 持有一个 C 对象。独立测试替身实测 1/2/4 workers、两种访问顺序、GIL 释放、owner 保留和并行重入拒绝。 [源码与接入](INTEGRATION.md)
- 完成独立模块诊断微基准。真实公共 fixture 的 24 行按原值平铺为三个尺寸，计时包含绑定校验、输出分配、求值和 error 扫描。原始区组时间见记录，适用范围为本机热缓冲串行模块。 [原始计时](evidence/b23-microbench.json)

## 运行证据

WSL2 Ubuntu x86-64，glibc 2.43、GCC 15.2.0、CPython 3.12.16、NumPy 1.26.4、SciPy 1.14.1、tqdm 4.66.6。对 10,000 次原版调用逐次比对高斯值和完整随机状态，其中 9,090 行可访问数值输入分别跑两种生产布局，覆盖 1,217 个 normal 空单和 910 次不可访问调用。两布局回填的订单字段和 `float.hex()` 均一致。24 条公共 FCN 行按捕获值回放，两个布局逐位匹配订单结果。 [实际命令、退出码与日志](evidence/b23-validation.txt)

跨主机诊断发现两条关联记录的 `z_noise` 相差 1 ULP，均为调用索引 10。原 ARM64 fixture 是 `-0x1.f631d79e012bep-1`，本机重算是 `-0x1.f631d79e012bdp-1`。MT 状态和高斯缓存是否存在均与保存值一致。生产公式的本机位级验收仍按原判据执行。 [原因与范围](RESEARCH.md)

## 待集成与停止位置

| 状态 | 工作与责任 |
| --- | --- |
| `INTEGRATION_PENDING` | D 的生产 packing 和独立 ABI 回执，A 按公共契约接入真实批次、随机流和订单回填。 |
| `INTEGRATION_PENDING` | C 的生产 `run_ranges` 和持久 Taskflow 执行器，接入与核对按 GIL 审计和接口示例执行。 |
| `INTEGRATION_PENDING` | E 的独立整机差分与首差报告，组长跨模块验收。 |
| `NOT_RUN` | B4/B5 和正式端到端性能实验，等待组长的后续任务及统一协议冻结。 |

[接入签名、示例和验收步骤](INTEGRATION.md) · [研究记录](RESEARCH.md) · [论文方法草稿](PAPER_NOTES.md)
