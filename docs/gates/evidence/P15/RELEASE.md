# FINAL 发布候选与剩余风险

**建议暂缓公开 Release。** 当前材料供内部检阅，正式 FINAL 仍为 BLOCKED。远端 main 为 `e2492a4b8317c6674918b13470b577f4d6f8675d`，PR #1 仍是 `f867a4fb07c928f459fa8b6d3e84a95ee88b1742` 的 Draft。生产 `92f8bbf08da514dcb24e27b6a815d3947c352798` 无托管 Actions 记录，未发现 GitHub Release 或 Actions 产物。远端保持原状态。

## 内部候选

本地 `codex/p15-final-audit` 含源码、锁和 P15 审计。内部包 `CoreOrder-P15-audit-source.bundle` 保留可达历史与三个 gitlink，依赖通过固定上游递归取得。随包 JSON 记录文档候选、实际受测、生产及 pilot SHA，还有源码包与离线包哈希，正式实验身份留空。依赖 wheel、构建缓存、原生扩展与本机大体量运行目录保留在源码包外。

`CoreOrder-P15-offline-demo.tar.gz` 是第三次实跑的独立 PAMS 与四 worker 候选轨迹、对照回执及校验清单。P15 原始构建和三次 Demo 位于本工作树 `results/acceptance/final/p15/`。E 的完整历史 `CoreOrder_E1-E3.bundle` 仍缺。 [离线重放](DEMO.md) · [E 原归档校验](../../../roles/E/EVIDENCE_ARCHIVE.json)

| 检查 | 实际结果 |
| --- | --- |
| PAMS 0.3.0 | `6cd53810103780770c5b5d6ee0069ccab9f4b358`，EPL-1.0。保留许可逐字节匹配，派生恢复源码有 SPDX、原路径和 SHA。 |
| Taskflow 3.11.0 | `816b4ad53b44196c88f409eb7b4a25a0e3bfdf42`，MIT。固定头文件与许可副本已核。 |
| pybind11 2.13.6 | `a2e59f0e7065404b44dfe92a28aca47ba1378dc4`，BSD-3-Clause。固定上游、实际绑定和许可副本已核。 |
| 源码和依赖 | CoreOrder EPL-1.0。wheel 按 lock 安装，未见 marketsim-hpc、JAX-LOB 源码或构建临时二进制入树。 [第三方说明](../../../../THIRD_PARTY_NOTICES.md) |
| 凭证与体量 | 基线跟踪文件和原私有工作树的一个未忽略脚本均未命中高置信私钥、常见 GitHub token 或 AWS access key 模式。审计候选可达历史无单个至少 1,000,000 B 的 blob。 |
| 本机路径 | 审计基线有 18 个跟踪文件含绝对路径，包括候选协议锁和旧记录。本地原始环境也含宿主字段。保持证据原件与哈希，公开范围需单独审查内容和可达历史。内部 bundle 保留这些历史。 |
| 已有开发 | 原工作树的未跟踪 E 复验脚本保持原样。P15 仅在独立 worktree 更新 README、审计与现有 CLI Demo 驱动。 |

## 正式放行

1. A/E 修复配置身份、量测字段及验证回执引用，保存最小反例并重新验收受影响的 G0–G2。组长核对托管 CI 与签名。
2. E 在有授权的目标设备完成全部保留配置的 V01，提交绑定二进制、SHA、环境的生效 G3 和正式采集/统计入口。按原矩阵保留成功、失败、超时与缺测。受测条件或计时边界改变时，执行 G3 重测规则。
3. E 收集非模块作者独立回执，B/C/D/E 补齐定稿与课件，完成汇编论文、团队 PPT 及全员实际彩排。
4. 组长复核公开范围、宿主字段、数据权限及可达 Git 历史。推荐候选名 `coreorder-r4-course-rc1`，实际 tag 与 Release 取正式签认和用户授权。
