# P09 五后端系统集成

**2026-11-25（上海时间） · 代表性系统差分 27/27 PASS · G2 候选提交 `92f8bbf08da514dcb24e27b6a815d3947c352798`**

从 P08 `dff78073b2c467d653ff0b57c83300fba23fc052` 建立 `codex/p09-system-integration`。固定契约为 `coreorder-r4-v1`，PAMS 为 `6cd53810103780770c5b5d6ee0069ccab9f4b358`。验收在 macOS 27.0 arm64、CPython 3.12.11、NumPy 1.26.4、Apple Clang 21.0.0 完成。正式 G0 与 G1 签认仍待完成，G2 当前为候选。 [P09 实跑证据](evidence/P09.txt) · [G2 状态](../../gates/G2.md)

## 成员交付与接入

| 来源 | 实际接入与复验 |
| --- | --- |
| B `f8d2be9f1391ac5e430112665efaff7bb844c507` | 生产 FCN 核与绑定按原交付 SHA 使用。组合扩展独立运行 B 的 18 项适用测试，13 项测试执行器专用用例跳过。原串行扩展拒绝并行的专用用例用组合绑定的参数和真实执行器验证替代。 |
| C `5ad1ecb78272ff2564075cf01a90df252ae7e7ba` | `native/runtime/` 以本地接收提交 `b3e856072a313022eb693f12468caf3aa60b8de5` 收入，文件与 C 原分支一致。独立 CTest 4/4。C 的 FCN 测试 fixture 仅用于该模块回归。 |
| D `decccbf55955e3fbeb4bbe5266eb0c2b043b3f75` | 生产 live packing 和租约原样接入。独立布局测试 13/13，真实基本面冲击配置的 24 行回建与原版逐位一致。 |
| E `b05d5555fa5cc756a91ab61c644e797ca227c26f` | 使用 P04.5 已接收的 collector、codec、compare 和 invariants。独立参考进程核验固定 PAMS 的文件并从该 vendor 运行。在实际生产 CLI 进程采集 E 同一观察结构，逐事件、逐状态、逐 RNG 比较。 |

重新读取远端分支，A/B/C/D/E 与 P08 所见头提交一致。GitHub 可读取的 PR 列表仅有 Draft #1。Git 另公布 `refs/pull/2/head` 指向 C 交付，但 PR #2 元数据查询返回 404，未计作已审核。B/D/E 均按真实 Git 交付提交核验。 [PR #1](https://github.com/DengJunxian/CoreOrder/pull/1) · [分支与构建记录](evidence/P09.txt)

根构建用 A 的模块注册点将 B 的 `ExecutorFactory` 接到 C 的持久执行器，同一扩展链接 B 的唯一 `evaluate_range` 和 C 的 Taskflow 静态库。构建保留 C++17、`-fno-fast-math -ffp-contract=off`。加载的扩展 SHA-256 为 `fc68cbeee0caf58e9f248de1d210dc69ad875ced0f20c99110b9af6f395893d7`。PAMS 与项目源码依 EPL-1.0，固定 Taskflow 依 MIT，pybind11 依 BSD-3-Clause。 [许可证与出处](../../../THIRD_PARTY_NOTICES.md)

## 后端能力

| 后端 | 执行路径 | workers | 原生布局 | 堆恢复 |
| --- | --- | --- | --- | --- |
| `py-seq` | 原 PAMS SequentialRunner | 1 | — | upstream / incremental |
| `py-thread` | 原 PAMS MultiThreadAgentParallelRunner | 正整数，本轮验证 2 | — | upstream / incremental |
| `py-process` | 原 PAMS MultiProcessAgentParallelRunner，固定 spawn | 正整数，本轮验证 2 | — | upstream / incremental |
| `native-serial` | B 的 direct loop，每次 run 创建 0 个 Taskflow executor | 1 | AoS / SoA | upstream / incremental |
| `native-parallel` | 同一个 B 核，C 每次 run 创建并复用 1 个 Taskflow executor | 正整数，本轮验证 1、2、4 | AoS / SoA | upstream / incremental |

原生普通代理限制为确切类型 `FCNAgent`，市场为原 `Market` 或增量模式启用的 `CoreOrderMarket`，高频代理为原 `MarketMakerAgent`。CLI 记录请求与实际后端，其他类型或冲突选项显式退出。PAMS 的 Python 线程和进程执行由上游实现。进程模式保留原配置，运行层约束 workers 与 spawn。进程证据记录实际父端出队的序列化任务数、字节和管道发送用时。normal 双市场每种堆模式发送 28 个任务，分别为 2,462,968 和 2,464,554 字节，管道用时不含 pickle、子进程收取和反序列化。仿真总时段包含上游分发和等待，单独序列化耗时未分解。 [进程诊断与命令](evidence/P09.txt)

激活和市场遍历留在原 PAMS 顺序中，主线程按调用顺序准备 Gaussian。D 每批读取真实状态并租出同容量缓冲。B 在持 GIL 时检查 buffer 和持有 owner，C 只接收纯 C++ 范围回调和独占输出槽。同步 barrier 返回后，A 用 sidecar 按原调用和市场顺序重建真实 Order。上游继续检查、提交和处理订单，并执行 HFT、撮合、事件与账户更新。增量路径仅用 A2 的已审查市场适配器替代同一市场角色，E 观察记录移除该角色上唯一新增的 `book_restore` 运行字段后作结构比较。

P08 错误行遮蔽在 A 的打包边界修复。D 未能完成整个 batch 时，A 在原独占租约内用同一生产 evaluator 检查已完整写入的前缀。前缀若有更早数值错误，保留该行错误，否则保留 D 的首个打包错误。失败批次随即退出，前缀结果不回填，不追加抽样，不切换后端。该错误路径依赖 D 当前的写入计数和存储字段，后续可由 D 的正式前缀接口替换。最小反例在两种原生后端、两种布局均退出 1，并报告 `FCN row 0 failed with error 1`。另有 4 个合法前缀的对照用例保留第 1 行 packing 错误。 [回归用例](../../../tests/platform/test_native_serial.py) · [P08 首差](../../gates/G1-native.md)

## 实测矩阵

| 完整工作负载，seed 42 | 候选运行 | E 每次比较范围 |
| --- | ---: | --- |
| normal 双市场、M=0→3、空补批、稀疏访问、HFT 与冲击 | 22 | 184 条事件、10 个检查点、初态、终态及完整 RNG |
| CI2002 fixed、单市场、M=1 | 3 | 260 条事件、81 个检查点、初态、终态及完整 RNG |
| fixed、4 个代理、M=N | 2 | 52 条事件、7 个检查点、初态、终态及完整 RNG |

27 次实际 CLI 运行全部通过 E 精确结构比较及不变量。各负载内 CLI 交易 trace、终态和 RNG 哈希也一致。normal 负载覆盖五后端、两种堆、两种布局，原生并行 workers 1/2/4，用 static 和 dynamic。项目 pytest 92/92，根 CTest 2/2。另在组合扩展上复跑 P08 的 10,181 个有效数值样本，生产 binding 验证 72 个布局、大小与分块组合，以及 6 个失败后复用对照。 [证据与命令](evidence/P09.txt)

~~~sh
PYTHONPATH="$PWD/build" .venv/bin/python -B -m coreorder validate --suite g2 \
  --output results/acceptance/g2/representative-rerun
~~~

本次原始产物位于 `results/acceptance/g2/p09/`。候选目录包含每个运行的命令、stdout/stderr、退出码、manifest、E 完整 trace、差分与汇总。E 的正式完整矩阵和签认、当前 SHA 的托管 CI、sanitizer、其他主机与正式性能均待对应阶段。P09 到此停止。

---

## P07 原生串行最小闭环

**2026-11-25（上海时间） · 本地端到端复验 PASS**

以 P06 `74af43df602d6ac95220c107790e0900abd4a649` 为输入，受测源码 `da29dd6d4d80ffd1afebb059941a27e790a10070`，契约 `coreorder-r4-v1`。P04.5 本地 G0 和 P06 本地 G1-heap 技术验收已通过。正式 G0 仍待冻结，GitHub `main` 为初始化提交，PR #1 为 Draft。P07 将两条路径的堆恢复均固定为 `upstream`，单独验证普通订单决策接入。 [G0](../../gates/G0.md) · [G1-heap](../../gates/G1-heap.md) · [PR #1](https://github.com/DengJunxian/CoreOrder/pull/1)

## 实际接入与来源

| 角色 | P07 使用的接口 |
| --- | --- |
| A | `NativeSerialRunner._collect_orders_from_normal_agents`。`SequentialRunner` 继续运行原 `_setup`、`_iterate_market_updates`、`_handle_orders`、HFT、订单处理、撮合与账本。`run_py_seq` 保留上游默认入口，原生串行调用显式选择适配器。 |
| B | `f8d2be9f1391ac5e430112665efaff7bb844c507` 的 `native/fcn/` 和 `native/bindings/`。根 CMake 用固定 pybind11 构建 `_coreorder_fcn`。`Evaluator(parallel=False).aos` 同步调用真实 `evaluate_range[0,n)`。 |
| D | `decccbf55955e3fbeb4bbe5266eb0c2b043b3f75` 的 `packing.py`。每个 run 创建一个 AoS `LayoutBuffer`，每批用 `pack_batch` 从当前 PAMS 对象填入 112 B 行。pack 消费 A 提供的 `Draw`，并返回 `(agent_id, market_id, call_index)` 和有效期覆盖 C++ 调用的借用视图。 |
| E | P04.5 收到的 E1/E2 参考和比较器，源自 `b05d5555fa5cc756a91ab61c644e797ca227c26f`。参考进程逐 blob 核验、装载固定 PAMS 源码 `6cd53810103780770c5b5d6ee0069ccab9f4b358`。 |

B、D 的接收路径均与源提交逐字节一致。根扩展只编入 B 的生产绑定与数值核，持有输入至同步返回后再回建。Release 实际编译以 Apple Clang 21.0.0、C++17、`-O3 -fno-fast-math -ffp-contract=off` 完成。本机扩展 SHA-256 为 `6575e0176fd3d8bfe1e9985fc380f7d31e7d1e38882ce1325b41d7b9a15ed26c`，加载扩展后的运行环境记录包含加载路径、ABI 版本和该二进制哈希。 [源码许可](../../../THIRD_PARTY_NOTICES.md) · [实际编译与运行日志](evidence/P07.txt)

## 配额、采样与回建

1. 从原 `normal_frequency_agents` 列表调用一次 `self._prng.sample(agents, len(agents))`，保留原激活顺序。额度为 0 时仍执行这次 sample，普通代理不会进入决策。
2. 取剩余非空代理名额 `r = maxNormalOrders - len(all_orders)` 内的连续前缀。每个代理至多贡献一个非空订单列表，因此宽度不超过 `r` 时，原串行在批尾前不可能用尽名额。空结果按原排列补批，直到额度用尽或遍历结束。一个代理返回多市场订单仍只占一个名额。
3. 在 Python 仿真线程按批内代理顺序和 `simulator.markets` 原序取样。不可访问的市场跳过。fixed 对每个可访 pair 调一次 `gauss`，normal 调两次，包括数值核判为空单的行。直接使用代理已有的 `random.Random` 和其 gauss 缓存。
4. 每批从当前市场和代理状态 pack。采集普通订单期间没有提交，原 step hooks 与 HFT 继续在上游位置作用于市场。同步核返回后，用 D 的行身份映射到原调用槽，使用绑定的 `price`、`side` 和打包的 `window` 创建 `Order`，`volume=1`、`kind=LIMIT_ORDER`，TTL 为原窗口。组内保持市场原序，非空组交原 `_check_submitted_orders` 与 `_handle_orders`。

CLI 支持 `native-serial/aos/upstream`、一个 worker、原版普通 `Market` 和确切 `FCNAgent`。原版 `MarketMakerAgent` 走继承的 HFT 路径。缺扩展、SoA、增量堆组合或额外 worker 退出 2。普通 FCN 子类在 setup 后被拒，真实 B 行错误中止整个 run 并保持 `backend_effective=native-serial`，退出 1。故障测试均未写出金融事件和最终 RNG 回执。 [实现](../../../src/coreorder/native_serial.py) · [边界回归](../../../tests/platform/test_native_serial.py)

## 两个完整市场

同一份原始配置、seed 42、`book_restore=upstream`。两条真实 CLI 路径逐条比较交易事件、逐市场与逐步状态，最终市场历史、账户、逻辑簿和完整 RNG 文件逐字节一致。E 另采集两条运行路径，并各自与验证过的原版 PAMS 比较初末状态、有序日志、逐步检查点与全量 RNG，同时校验守恒。所有对照均通过。

| 工作负载 | 市场 / 全局步 | 订单 / 成交 / 过期 | E 日志 / 检查点 | 普通调用 / 原生行 / Gaussian 调用 |
| --- | ---: | ---: | ---: | ---: |
| CI2002 fixed、M=1 | 1 / 80 | 80 / 14 / 0 | 260 / 81 | 80 / 80 / 80 |
| normal 双市场，M=0 → 3 | 2 / 9 | 89 / 28 / 25 | 184 / 10 | 35 / 57 / 114 |

normal 配置含 12 个普通代理与 1 个原版做市代理。第 0 步没有订单。随后 8 步每步恰有 3 个普通代理返回非空列表，各产生 4–6 笔普通订单，共 41 笔。35 次普通调用产生 **11 次空列表**，原生收到 57 行，其中 16 行方向为空。普通批次共 15 批，宽度 1–3。原版 HFT 另提交 48 笔，第 3 步 MarketA 的基本面由 300 变为 270。 [fixed 配置](../../../configs/workloads/smoke.json) · [normal 配置](../../../configs/workloads/native-serial-normal.json)

项目 pytest **84/84**、根 CTest **2/2**。B 的串行绑定指定测试 **19 项通过、13 项并行替身专用测试跳过**，实测 9,090 个有效行及 910 次不可访问控制。D 的布局 pytest **13/13**，24 条公开行和真实事件 packing 回放通过。B 的 G1-native 万条有效样本要求、G0 正式签认和 G1-native 整体门仍按对应阶段处理。生产 Taskflow、SoA、native 与 incremental 组合和正式性能 **NOT_RUN**。 [执行日志](evidence/P07.txt)

## 复现

~~~sh
.venv/bin/cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DPython_EXECUTABLE="$PWD/.venv/bin/python"
.venv/bin/cmake --build build --parallel 2
PYTHONPATH="$PWD/build" .venv/bin/python -B -m pytest -q
PYTHONPATH="$PWD/build" .venv/bin/python -m coreorder run --backend native-serial \
  --config configs/workloads/native-serial-normal.json --seed 42 --output results/native-normal-rerun
~~~

本地原始证据在 `results/acceptance/p07/full-markets/`，含两个工作负载的真实 CLI manifest/metrics/status、有序 trace、最终 RNG、E 压缩参考与候选结构、比较回执和 `summary.json`。同级 `audit_p07.py` 复现两套全量对照，输出目录使用新路径。 [可提交的执行记录](evidence/P07.txt)
