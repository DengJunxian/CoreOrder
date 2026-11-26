# G1-native 生产原生串行验收

**2026-11-25（上海时间） · 两套有效市场精确差分 PASS · G1-native BLOCKED · 完整 G1 BLOCKED**

P08 从 P07 交付提交 `313ebaba8b59c63fcc4fb5cff1e57d99aaec881f` 建立独立工作树 `codex/p08-g1-native-acceptance`。验收限定 `native-serial / aos / upstream / workers=1`，契约 `coreorder-r4-v1`。受测 PAMS 为 `6cd53810103780770c5b5d6ee0069ccab9f4b358`，vendor 干净。B 的核与绑定、D 的 packing 与各自交付逐字节一致。E 的工具为 P04.5 接收版，P08 未改生产路径或验证规则。环境为 macOS 27.0 arm64、CPython 3.12.11、NumPy 1.26.4、Apple Clang 21.0.0。 [P07 接口](../roles/A/INTEGRATION.md) · [P08 实跑日志](evidence/P08.txt)

## 验收矩阵

| 检查 | 结论 | 实测与源码依据 |
| --- | --- | --- |
| 生产动态库与 direct loop | PASS | 真实 CLI 的 manifest 有效后端为 `native-serial`，environment 记录实际加载的 `_coreorder_fcn.cpython-312-darwin.so`、R4 ABI 和 SHA-256 `6575e0176fd3d8bfe1e9985fc380f7d31e7d1e38882ce1325b41d7b9a15ed26c`。构建只链接 B 的模块、绑定与数值核，使用 C++17、`-fno-fast-math -ffp-contract=off`。原生注册不提供 executor factory，串行走 `evaluate_range(0,n)` 逐行循环，生产模块拒绝 parallel 请求。 |
| 共享 ABI | PASS | C++ `sizeof/alignof/offsetof` 与 NumPy 字节互读通过。AoS 输入 **112 B / 对齐 8 / stride 112**，10 个 float64 偏移 0–72、3 个 int64 偏移 80/88/96、2 个 int32 偏移 104/108。输出 **16 B / 对齐 8 / stride 16**，偏移 0/8/12。两侧均为本机小端。D 三个 int64 身份字段独立存于 24 B sidecar。 |
| GIL、owner 及串行重入 | PASS | pybind11 在 GIL 下检查并持有输入 owner、分配输出，释放 GIL 后同步访问纯数值内存，恢复 GIL 后扫描错误和返回结果。D 的 lease 覆盖整个同步调用及回建，在 95 个真实批次中复验输入只读、借出期间拒绝 refill，以及输出独立且跨批次保持原字节。B 的同一串行实例并发调用回归通过，A 的单个 runner 仍由单一仿真线程驱动。 |
| 数值与分支 | PASS | 对照固定 PAMS 逐行核过倍率、倒数、求和顺序、log/exp、chart 正负、fixed 分支与 normal 空方向仍计算价格。**10,181** 个有效行逐位比对订单价和字段，另有 **1,019** 次不可访问控制。覆盖四种 margin × chart 符号组合、time=0、零窗口诊断、同一代理连续多市场、56 个初始 Gaussian 缓存已填充的代理和 1,360 个 normal 空方向行。沿用 B 测试生成逻辑，只在 P08 审计进程把代理数从 100 扩至 112，expected 仍由原版 FCN 生成。每次调用核对 Gaussian 十六进制结果及完整 RNG 状态。 |
| 激活、市场访问、回建与上游处理 | PASS | 读取同一原版 `sample`、捕获前后完整 runner RNG 和返回身份顺序，比较激活、市场访问、主线程每次 `gauss` 的值及前后状态。复核上游 `_check_submitted_orders`、`_handle_orders` 参数包含原组序、身份、类型、方向、量、TTL 和价格 hex。normal 配置测试 M=0 后切到 M=3、访问不全、空结果补批、单代理多市场、原版 HFT 与基本面冲击。 |
| 完整市场对照 | PASS | 两套实际 CLI 运行逐事件、逐步、终态与最终 RNG 相等。E 在隔离进程核验并加载原版 PAMS，分别与两种真实运行方式的完整观察结构精确比较。初态、逻辑订单簿、历史、账本和逐步 RNG 均一致，三侧不变量通过。 |
| 无效 ABI 及显式拒绝 | PASS | B 实测错 dtype/大小、结构对齐、shape、非 ABI stride、异端序、C 连续但地址偏移 1、未对齐位、非法 worker 和数值错误。项目实测无扩展、错误代理子类、单独零权重行，额外 CLI 实跑 2 workers、SoA 和 incremental 选项均以非零显式拒绝，未生成成功交易或成功 RNG 回执。 |
| 跨 packing / C++ 的最早失败行 | **FAIL** | 两行都非法时，CLI 先报告第 1 行 packing 未通过，遮蔽第 0 行。把同一份实际捕获的行字节传给生产绑定，绑定正确报告第 0 行。故障 run 已中止，且始终保持请求的原生后端。 |
| 正式签认 | **BLOCKED** | 先修复最早失败行，再复验并取得含 E1 的共同 G0 冻结和 E 复核回执。PR #1 仍为 Draft，现有 Ubuntu PR 成功属于早期 A 候选。 |

B 的独立回归 **19 项通过、13 项测试 executor 专用项目跳过**。D 模块回归 **13/13**，公开 ABI 回放 24 行、真实 PAMS 基本面冲击回放 24 行。项目 pytest **84/84**，根 CTest **2/2**。E2 本人交付记录是 `MODULE_PASS / INTEGRATION_PENDING`，本次组长复跑了其参考和差分工具，对应进程、回执与快照已落盘。 [E 的交付记录](G1-E.md) · [实际日志](evidence/P08.txt)

## 完整市场实跑

原配置逐字节相同，seed 42，双方 `book_restore=upstream`。

| 负载 | 市场 / 全局步 | 订单 / 成交 / 过期 | E 事件 / 检查点 | 普通代理调用 / 原生行 / gauss |
| --- | ---: | ---: | ---: | ---: |
| CI2002 fixed | 1 / 80 | 80 / 14 / 0 | 260 / 81 | 80 / 80 / 80 |
| normal 双市场 | 2 / 9 | 89 / 28 / 25 | 184 / 10 | 35 / 57 / 114 |

fixed 每批 1 个普通代理，34 次 Gaussian 调用复用已填充的缓存。normal 实际执行 15 批，宽度 1–3。70 次市场访问中 13 次不可访问，均跳过 Gaussian。57 次 Gaussian 调用前缓存非空，11 次普通代理调用返回空列表。观察运行逐次记录完整 MT 状态与缓存 hex，在配额用尽处停止。 [全市场日志和哈希](evidence/P08.txt)

## 首个分歧与责任模块

用一个原版市场、两个确切类型的 FCNAgent、一步、M=2、seed 3 复现。第 0 行 `(agent_id=0, market_id=0, call_index=0)` 的三项权重为零。第 1 行 `(1,0,1)` 的 JSON 均匀界限为两个有限数 `[-1e308, 1e308]`，固定 PAMS 在 setup 计算跨度时溢出，得到 `noise_scale=inf`。原版首先在第 0 行除零，同批实际捕获的两行交给 B 也首先报告第 0 行。生产 CLI 却以 `ValueError: row 1 (1, 0): non-finite numeric field` 结束，违反 R4 公共技术契约 §4.7 对最早失败行的要求。三个 CLI 对照均退出 1，未写金融事件或最终 RNG，原生两例未回退。 [最小配置](evidence/p08-first-failure.json) · [完整契约入口](../CONTRACT.md) · [首差与原始命令](evidence/P08.txt)

**责任归 A 的批次编排与 D 的前置校验边界。** D 在 `pack_batch` 中按行检查有限数并中止整个打包，A 因而无法交付已打包的前缀。B 的绑定在同一输入中正确选第 0 行。A 和 D 应共同确定如何保留更早行的诊断，B 复验绑定的行错误顺序和整批无回填，E 用最小配置重新裁决。P08 为独立验收，生产修复 **0/2**。 [A 批次调用](../../src/coreorder/native_serial.py) · [D 打包边界](../../src/coreorder/packing.py) · [B 错误扫描](../../native/bindings/fcn_binding.cpp)

~~~sh
PYTHONPATH="$PWD/build" .venv/bin/python -B -m coreorder run \
  --backend native-serial --book-restore upstream --seed 3 \
  --config docs/gates/evidence/p08-first-failure.json \
  --output results/p08-first-failure-rerun
~~~

独立调用与租约复验可以从本分支重复执行。数值审计额外需要 B 的固定 checkout。

~~~sh
PYTHONPATH="$PWD:$PWD/build" .venv/bin/python -B docs/gates/evidence/replay_p08.py \
  calls results/p08-calls-rerun
PYTHONPATH="$PWD:$PWD/build:$PWD/vendor/pams" .venv/bin/python -B \
  docs/gates/evidence/replay_p08.py numerical results/p08-numerical-rerun /path/to/member-B
~~~

P08 原始记录在 `results/acceptance/g1-native/p08/`。`full-markets/` 有 CLI 回执、完整 E 参考与候选快照，`calls/` 有原顺序、完整 RNG 和调用记录，`failure/` 有首个分歧、两行 hex、原始配置和 Gaussian 前后状态。初轮审计脚本的两处错误已保留，数值进程当时从安装目录导入 PAMS，而 B 工具要求 vendor 根。逐调用对照最初把观察记录传给完整运行 schema。改为在数值进程显式导入固定 vendor 并调用 E 的结构比较原语后复跑。正式 G0 与 G1-heap 的共同基线和签认仍待完成，**完整 G1 BLOCKED**。 [补充审核脚本](evidence/replay_p08.py) · [G0](G0.md) · [G1-heap](G1-heap.md)
