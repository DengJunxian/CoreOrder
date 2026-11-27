# R3 生产正确性与验收证据

受测源码为干净提交 `88fee6f1dafeeabc44750913fa2e59d518a3e1e5`，从 R2B `d49bb2d47abb7aa1726be822b5aa819cdf6f8c5a` 建立独立 worktree。Apple M5 使用 macOS 27.0 arm64、CPython 3.12.13、Apple Clang 21。新目录构建的 Release 扩展与实跑加载文件的 SHA-256 均为 `fc74f6e6b43cdbce3408361b53512e4e200fdfd94b2acbfb1f2cd0727d3f524b`。保留实际编译命令，其中数值核使用 C++17、`-O3 -fno-fast-math -ffp-contract=off`。 [机器可读证据](verification.json)

| 门禁 | 本机验收 | 正式状态和所需签认 |
| --- | --- | --- |
| G0 | PASS。固定上游、许可、独立构建、真实 fixture、ABI、schema、官方 PAMS 和 E1 全部通过。 | BLOCKED。同一候选的托管 CI 为 NOT_RUN，A、E 及 B/D 的共同基线回执待取得。 |
| G1-heap | PASS。P06 的 23 对完整仿真和 8 个定向边界，以及成员 E 原版工具的 38 对重跑全部通过。 | BLOCKED。待 G0 共同签认和 E 对同版本堆证据的复核。 |
| G1-native | PASS。10,181 个可访问 FCN 数值行、两个布局的逐位对照和 6 条真实串行闭环通过。 | BLOCKED。待 G0 和 A/B 交叉审阅、D ABI 与 E 独立复核签认。 |
| G2 | PASS。56/56 通过 E 语义差分、E gate 和 E 记录校验。取得三份可按真实 run ID 追溯的本机 C01 候选回执。 | BLOCKED。待共同 G0/G1、E 与非作者签认，以及自动整 run fallback 的范围决定。 |

## 成员回归与版本归属

B 的行级数值、两个布局的绑定、无效 buffer 和 GIL 持有测试来自 `f8d2be9f1391ac5e430112665efaff7bb844c507`。原 PAMS 数值采样生成器扩展到 112 个代理，输入消费和逐值判据沿用原版。串行测试验证 0 个 executor，持久并行每实例创建 1 个。B 的测试替身在生产绑定测试中由实际 Taskflow 执行器替换。 [B 原始交付](https://github.com/DengJunxian/CoreOrder/tree/f8d2be9f1391ac5e430112665efaff7bb844c507/tests/native)

C 的 C2/C3 调度、range、异常和持久性测试取自 `5ad1ecb78272ff2564075cf01a90df252ae7e7ba`，链接当前 `NativeExecutor` 和生产 `evaluate_range`。D 的 ABI 双向字节、租用和 live event 回放取自 `decccbf55955e3fbeb4bbe5266eb0c2b043b3f75`。D 在同一真实事件配置比较了冲击前 10 行、冲击后 14 行。 [C 原始交付](https://github.com/DengJunxian/CoreOrder/tree/5ad1ecb78272ff2564075cf01a90df252ae7e7ba/tests/platform) · [D 原始交付](https://github.com/DengJunxian/CoreOrder/tree/decccbf55955e3fbeb4bbe5266eb0c2b043b3f75/tests/layout)

E 的已入库轨迹、比较器、守恒和注入测试均保留。G1 另从成员 E 的 `b05d5555fa5cc756a91ab61c644e797ca227c26f` 导出原样独立模块。G0 故障注入检出调换事件、一位价格差和少一次 Gaussian 抽样。后二者分别定位到价格 hex 和逐步状态中的 Gaussian 缓存。 [E 原始交付](https://github.com/DengJunxian/CoreOrder/tree/b05d5555fa5cc756a91ab61c644e797ca227c26f/validation)

## 回执、边界与故障

旧的 1 市场、1 代理、1 步、seed 42 反例已通过。原配置字节哈希为 `752c46c00a828661bbbf46b3e08f7534b5cb52d5e55e26b2e31de0719df430c2`。E 所需的规范化配置哈希为 `6741e70be699f243372ccc89bb5c4b229a25cff26eacbb829783c67f1288f6a3`。两者在生产记录分别保存，回填错误的规范化字段时 E 在身份检验即拒绝。运行器复验原始和有效字节，E 对解码工作负载继续执行逐事件、逐步、初末态及完整 Python/NumPy RNG 比较。正式性能资格另由 G3 决定。

原生研究范围涵盖普通 PAMS Market、CoreOrderMarket、精确 FCNAgent、已验证的上游 MarketMakerAgent HFT 和无费场景。含费用的两市场探针有 28 笔成交，生产与固定 PAMS 的公共观察一致。E 的独立状态编码对 `ProportionalTransactionFee` 显式报错，因此该能力仍为范围外。遇到不支持的代理或市场时会拒绝，并在注入场景保存空事件流与退出码。

提交组长审查的范围变更建议是保留显式拒绝和运行前手动选择 `py-seq`，将自动整 run fallback 移出核心 G2 阻断。当前 CLI 对 `--unsupported-policy upstream` 退出 2。对同一不支持原生的代理配置，手动选择 `py-seq` 的真实运行通过 E 差分。安全的自动实现需区分能力拒绝与业务错误，明确有效堆恢复、以原 seed 从头执行，并将回退 run 排除在原生结果之外。待组长批准后同步公共契约。

首轮失败均归档。P06 审计的最终观察器引用、独立 P10 审计的导入顺序、CLI 孤立模式下的生产哈希导入已在定向复跑修正。普通 Python 的 ASan 加载失败记录退出 −6。预链接 ASan 的 CPython 启动器重试通过，7 个非法 ABI、数值错误或公共样本检查及真实市场差分均成功。解释器泄漏检测关闭，其他 ASan/UBSan 检查启用。实际 Taskflow 的 C2/C3 在 TSan 下均通过。

## 复现入口

从仓库根目录运行，使用 README 的锁定环境和 Release 构建。原始日志与回执位于 `results/acceptance/r3/final/`，初次失败在 `results/acceptance/r3/verification/`。机器索引中的工作树根路径以 `$COREORDER_ROOT` 表示，原始命令文件保有执行时路径。

```sh
export PYTHONPATH="$PWD:$PWD/build"
.venv/bin/python -m coreorder validate --suite g0 --output results/review-g0
.venv/bin/python -m coreorder validate --suite g1 --output results/review-g1
.venv/bin/python -m coreorder validate --suite g2 --output results/review-g2
.venv/bin/python tests/acceptance/audit_g2_boundaries.py results/review-g2-boundaries results/review-g2
.venv/bin/python tests/acceptance/audit_g2_interfaces.py results/review-g2-interfaces
```

目标 x86 的 C01/V01、G3 和正式性能实验均为 NOT_RUN。托管 CI 只验证过旧候选。 [PR #1](https://github.com/DengJunxian/CoreOrder/pull/1) · [旧版 Foundation checks](https://github.com/DengJunxian/CoreOrder/actions/runs/45567774938)
