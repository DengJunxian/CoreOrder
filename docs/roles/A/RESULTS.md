# P11 堆恢复机制与实验前 pilot

**2026-11-25 至 26（上海时间） · 本地诊断完成 · 正式 H01、E05 与 G3 尚未启动**

P11 在独立工作树运行 P10 的候选生产代码，候选源为 `92f8bbf08da514dcb24e27b6a815d3947c352798`，实跑工作树为 `3c344f765c6ff288abad2faa6081c921f0ee0f36`。固定 PAMS 为 `6cd53810103780770c5b5d6ee0069ccab9f4b358`，公共契约 `coreorder-r4-v1`。五种预先选定的工作负载使用 seed **11、29**。E3 的真实 `experiments.capture` 负责带超时的子进程和原始日志，另复跑 E 的 `experiments.diagnostic`。P10 的回执兼容和共同门禁仍待收口。 [G2 状态](../../gates/G2.md) · [命令与日志摘录](evidence/P11.txt)

## 机器与计量

| 项目 | 实测 |
| --- | --- |
| CPU 与拓扑 | Apple M5，Mac17,3，10 物理核及 10 逻辑核，4 Super + 6 Efficiency，24 GiB RAM。AC 供电，探测时系统未报告热或性能警告。 |
| 软件与执行设置 | macOS 27.0 arm64（26A428），Apple Clang 21.0.0，CPython 3.12.11。Release 产物由锁定依赖重建，C++ 严格使用 `-fno-fast-math -ffp-contract=off`。BLAS/OpenMP 六项线程环境设为 1。未固定 P/E 核亲和性。 |
| 频率 | 系统频率键未返回数值。`powermetrics --samplers cpu_power` 实际因需要管理员退出。标为未取得，频率数据为 null。 |
| 性能计数器 | `perf` 与 Valgrind 未安装，`xctrace list templates` 实际提示当前 Command Line Tools 无完整 Xcode。没有得到事件、可用权限或覆盖率。硬件 PMU 与 Cachegrind 均未采集。 |

完整仿真 elapsed 从初始化后至业务完成。低开销样本统一使用原版 PAMS `Logger`，关闭额外 trace、堆计数和调用剖析。终态及完整 RNG 摘要在仿真计时之外计算，进程 elapsed 另含启动、初始化、摘要与退出。不使用 profile 或计数运行的时间估计系统耗时。 [测量口径与汇总](evidence/P11.txt)

## 配对规模与时间

各对照使用同一金融配置与步数。W0 的 JSON 逐字节来自 vendor 的 CI2002 原件，保留 100 + 500 步和默认 M=1。其他点采用相同 FCN 参数，并明确记录人口、名额、市场数与预热/交易步。两条 Python 恢复路径的有序金融事件、订单/成交计数、逻辑簿、账户、市场历史和终态 RNG 摘要一致。原生候选的等价证据也通过相同检查。未对事件序列重排。

| 负载 | N / M / K | 预热 + 交易 | 每 seed 订单 | py-seq upstream，仿真秒 | py-seq incremental，仿真秒 | native-serial incremental，仿真秒 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| W0-CI2002 | 100 / 1 / 1 | 100 + 500 | 600 | 0.026–0.027 | 0.021–0.022 | — |
| W4-START | 1,024 / 32 / 1 | 20 + 100 | 3,840 | 0.837–0.860 | 0.104–0.152 | 0.121–0.123 |
| W1-H | 4,096 / 32 / 1 | 20 + 100 | 3,840 | 0.871–0.916 | 0.143–0.143 | — |
| W2-H | 4,096 / 256 / 1 | 8 + 24 | 8,192 | 3.987–4.059 | 0.206–0.213 | 0.240–0.272 |
| W3-START | 16,384 / 1,024 / 4 | 2 + 8 | 40,960 | 25.134–26.028 | 1.017–1.062 | 1.182–1.208 |

低开销数值是两颗 pilot seed 各一次的观测范围。W2-H 和 W3-START 的 native-serial 在同一 incremental 基线上未显示进一步降时，W4-START 两 seed 结果方向不一，五个点都保留。W3 的原版进程已接近 30 秒限额，适合单独记录为高压力点。 [逐次运行与删失记录](evidence/P11-runs.csv)

## 恢复机制

`Market._collect_pending_executions` 暂取根订单后，剩余每侧仍是合法堆。上游拼接暂取与剩余容器并整体 heapify，incremental 逐项放回相同订单，再执行原版成交。诊断的每次恢复、买卖各侧均核对 `n=h+k` 和 `k/max(n,1)`。配对的双侧 n/h/k 原序完全一致。恢复次数按一次双方重建计，比较器计数仅包含恢复段内的 `Order.__lt__` 回调。

| 负载，seed | 恢复调用 | 双侧 Σn | 双侧 Σk | 买 / 卖 n 中位数 | 买 / 卖 k/n 中位数 | 恢复比较次数，上游 → 增量 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| W0-CI2002，11 | 201 | 8,929 | 848 | 21 / 22 | 9.524% / 9.091% | 14,610 → 3,286 |
| W0-CI2002，29 | 197 | 9,857 | 830 | 21 / 26 | 9.524% / 7.692% | 16,320 → 3,284 |
| W1-H，11 | 1,211 | 876,354 | 5,138 | 423 / 307 | 0.473% / 0.651% | 1,710,577 → 38,953 |
| W1-H，29 | 1,217 | 852,332 | 5,154 | 376 / 330 | 0.532% / 0.606% | 1,662,260 → 38,626 |
| W2-H，11 | 2,423 | 4,172,719 | 10,666 | 925 / 812 | 0.216% / 0.246% | 8,245,535 → 92,206 |
| W2-H，29 | 2,346 | 4,288,928 | 10,284 | 842 / 993 | 0.238% / 0.202% | 8,481,347 → 90,645 |

上游重建需要线性处理当前全簿，incremental 工作随实际暂取的订单量和当时堆深变化。观察到的高尾恢复仍需保留，用来检验 k 接近 n 时的边界。上游的两次 heapify 和 incremental 的逐项 heappush 在原始计数中分别验证。此处归因于恢复工作量，未得到硬件缓存计数。 [双侧分位数及次数](evidence/P11-heap.csv)

## 原版热点与增量后的成本构成

| W1-H，seed 11，分段诊断，秒 | py-seq upstream | py-seq incremental | native-serial incremental |
| --- | ---: | ---: | ---: |
| 普通代理选择与决策 | 0.9540 | 0.9848 | 1.0383 |
| Python FCN 策略，含 Gaussian | 0.1997 | 0.2094 | — |
| Gaussian API | 0.0139 | 0.0145 | 0.0136 |
| 原生随机准备，含 Gaussian | — | — | 0.0430 |
| packing 与借用 | — | — | 0.2489 |
| 原生求值调用，含绑定 | — | — | 0.0009 |
| 订单回建与释放借用 | — | — | 0.0378 |
| 上游处理与撮合，包含以下子项 | 12.3787 | 1.2473 | 1.1369 |
| 簿中提交 | 0.2146 | 0.2305 | 0.2104 |
| 匹配与暂取 | 0.3156 | 0.3653 | 0.3123 |
| 恢复段 | 11.4980 | 0.2942 | 0.2759 |
| 逐笔成交执行 | 0.2054 | 0.2063 | 0.1956 |
| 账本更新 | 0.0031 | 0.0030 | 0.0027 |

分段使用同一次带钩子的仿真，表内包含嵌套区间。恢复从原版待成交收集返回至首次进入 `_execute_orders`，包含拼接或逐项恢复以及区间内的控制开销。原生绑定包含边界检查、调用和错误扫描。带钩子仿真耗时为 13.471 / 2.372 / 2.314 s，与低开销样本分别记录。

W1-H seed 11 的独立 cProfile 中，原版 `_heapq.heapify` 累积 2.499 s，包含比较器；同次 profile 总量为 2.903 s。该函数计入其他上游调用处的 heapify，因此恢复专属耗时采用上表的恢复边界。增量后，仍有订单比较与撮合，且上游 `Random.sample` 累积 0.151 s，占该次 cProfile 0.473 s 的约 32%。原版每步对全部普通代理做激活排列；M 限制的是非空订单代理数。W1-H 共 120 个全局步、3840 次实际 FCN 请求。原生路径延续该采样成本，并在每批增加 packing 和回建。图表数据保留 `gauss` 到 API 调用层，命中缓存的调用也计入。

在这两次 Python cProfile 的计时口径内，若理想化移除全部 FCN `submit_orders` 时间、保持其他成本不变，条件 Amdahl 上界分别约为 **1.012**（upstream）和 **1.071**（incremental）。对应策略占比约 1.14% 与 6.67%。这两个值含 FCN 内随机调用的剖析成本，供选择诊断点。 [计时分段明细](evidence/P11-phases.csv)

另用 E 的紧凑日志对未修改的 W0 和 W1 各跑 summary 与 cProfile。两种观测产生相同事件摘要、终态与 RNG，且与 A 的金融事件计数一致。W0 小簿的 E profile 中 heapify 为 0.028 s，事件编码为 0.030 s。W1 的同套诊断中 heapify 为 2.557 s，体现热点随簿规模变化。

W2-H seed 11 的单独采集运行取得 8,192 条真实 AoS 行，按原调用顺序保存。Release C++ 对同一批输入重复 2,048 次，计时段只含生产 `evaluate_range`，实际累积 0.346748 s。每轮检查错误码，最终输出与真实绑定逐字节相等。输入哈希为 `f8894cd3585c9afe2b61ea2f3003751be21de19bd6012a69e4ff6a7845b0cf16`。该热输入 replay 与整机绑定阶段的调用次数和内存环境不同，分别保留。

B 的 24 行公共输入平铺微基准和 C 的替身内核微基准只供模块诊断。D 的独立 packing 样本只覆盖布局调用。E05 应使用本次真实采集的生产决策行及相同来源的布局转换，记录绑定开销、packing 和调度各自的边界。

## G3 冻结建议与预算

- **H01 保留 W0-H、W1-H、W2-H。** 实验中仅切换堆恢复。保留原版 M=1、小批次与中等批次三种几何，便于观察低恢复比例和高比例尾部。按协议安排 6 个条件 × 17 次为 102 次运行，维持 **55 分钟**阶段硬上限。以本机每个条件两 seed 中较长的完整进程 elapsed 计算，共约 **127 秒**的运行量级，作为本机容量检查。目标 x86 的耗时和有效预算仍需实测。
- **E05 保留 35 分钟上限。** 优先取 W0 的小批边界、W1 的恢复热点与迁移、W2 的生产 packing/replay。正式 replay 可预先固定同一次真实捕获的 128/512/2048/4096/8192 行前缀。若输入不足，缩减最大尺寸。核、布局与完整系统的诊断单独留档。目标机 PMU 未通过可用性与事件定义检查时，保留未测状态。
- **W3-START 作为后续 E02/E03 压力候选。** 当前 4 市场、每步最多 1024 个非空代理，受限记录完整保留。确认目标机后等步数复跑成对配置。避免按本机哪组耗时较低决定正式负载。
- **冻结前置项。** A/E 需收口 raw/canonical 哈希、来源字段和 `validation_run_id`，完成共同 G0/G1/G2 签认，再用目标 x86 主机的实际拓扑、频率、负载和超时证据运行完整 V01。V01 覆盖每个保留条件及五个正式 seed。E4 冻结入口和正式协议锁尚无本轮有效回执。本次交付为 G3 输入，保持共同 480 分钟预算与冻结程序。

原始目录为 `results/pilot/p11/`，含逐运行命令、stdout/stderr、退出码、环境、负载原件和实际有效设置、有序金融事件、剖析文件、双侧恢复原始记录、截止记录及 C++ replay。预检驱动曾尝试重复创建 E 的只读 ledger，修正为每个 workload/seed 独立 checkpoint 后重跑。预检数据和失败栈保留。完整 pilot 台账含 73 次主矩阵及复跑记录，71 次完成、2 次超时。W2-H 两次超时来自 30 秒的上游计数运行，按右删失保留。保持同一 JSON 和 seed 后，60 秒诊断限额下分别在 29.938 秒和 31.541 秒完成。26 次低开销运行均在 30 秒内，W3 的最慢低开销进程为 27.303 秒。

生产代码、队友模块与 oracle 均按受测候选保留。正式计时、PMU 归因、x86 复现、G3 冻结均为 `NOT_RUN`。P11 到此停止。

# P13 正式堆机制证据审查

**2026-11-26（上海时间） · 正式 H01/E05 BLOCKED · 新增正式运行 0 次**

G3 复核仍为 `BLOCKED`。`runnable=false`、`locked_for_execution=false`、`authorized_formal_runs=[]`，正式代码 SHA 和协议锁生效哈希均为空。目标 x86 主机尚无构建、环境或扩展回执，A/E 未签认，共同 G2 待收口，候选 V01 为 **0/140**。远端 E HEAD 为 `b05d5555fa5cc756a91ab61c644e797ca227c26f`，现有交付止于 E3。已查本地 CoreOrder 结果目录、交付包和 GitHub Actions 归档，未找到正式 H01/E05 raw 或 E4 分配给 A 的运行清单。 [G3 判定](../../gates/G3.md) · [E 交付](https://github.com/DengJunxian/CoreOrder/blob/b05d5555fa5cc756a91ab61c644e797ca227c26f/docs/roles/E/HANDOFF.md) · [复核日志](evidence/P13/audit.txt)

## 正式准入与结果

| 项目 | 候选范围 | 实际状态 |
| --- | --- | --- |
| H01 端到端 | W0-H、W1-H、W2-H，逐条件仅切换 `book_restore`。5 seed × 3 重复，共 45 个配对区组、90 次计时、12 次独立预热 | **NOT_RUN**，0 个可用配对。耗时、速度收益或负收益、95% 区间均无估计 |
| H01 正确性与工作量 | 每个正式条件及 seed，完整验证对原版 PAMS 的逐事件、状态、账户、订单与 RNG，并绑定 `validation_run_id` | **BLOCKED**，V01 无合格回执。P12 三个诊断 run 的 E gate/records 均拒绝 |
| E05 profile、阶段归因和 replay | 4 个 profile、80 条含预热的 replay 规划 | **NOT_RUN**，原版与增量的正式恢复用时、瓶颈迁移及核与封装的成本贡献均未测 |
| E05 PMU | 24 条候选，执行前确认主机事件定义、作用域及有效计数 | **NOT_RUN**，目标主机无 PMU 回执，缓存与访存收益无硬件估计 |

候选正式 seed 为 **101、202、303、404、505**。若获得正式记录，每个区组计算 `log(T_upstream/T_incremental)`，按 seed 取 3 次配对值的中位数，再对 5 个 seed 等权平均并取指数。采用预定随机种子 73021 按 seed 做 10,000 次 bootstrap。缺配对保留缺失，超时保留右删失。表中的 0 是准入计数，未测量值在机器可读表中保留为 `null`。 [正式结果状态表](evidence/P13/formal-status.json) · [候选计时清单](../../../configs/experiments/runlist-timing.jsonl) · [候选诊断清单](../../../configs/experiments/runlist-E05.jsonl)

## 可复算的 P11 机制证据

本轮从已存 raw 重新导出 **30,380 条**买卖双侧恢复观测，重算了 5 张原表，与原导出逐字节一致。W0-CI2002、W1-H、W2-H 各用 11、29 两个 pilot seed。六对 `py-seq` 的 `events.jsonl` 逐字节相同，订单数、逐类事件数、终态和 RNG 摘要一致。逐侧的恢复记录按原序相同，每条满足 `n=h+k` 与 `k/max(n,1)`。局部计数确认上游每次恢复对双侧各调用一次 heapify，增量路径的 heappush 次数等于双侧暂取订单数。原先两次 W2-H 上游计数超时及同输入的诊断复跑均在台账中。 [raw 索引与复算命令](evidence/P13/INDEX.md) · [逐侧表](evidence/P13/figures/heap-mechanism-pilot.csv)

恢复前的堆长度为 `n`，暂取 `k` 并保留 `h` 个订单。上游重建成本为 `O(n)`，逐项恢复最坏为 `O(k log(n+1))`。W1-H seed 11 的两侧深度中位数是 423、307，`k` 中位数均为 2，恢复比较从 **1,710,577 降到 38,953**。W2-H seed 11 的深度中位数是 925、812，`k` 中位数仍为 2，比较从 **8,245,535 降到 92,206**。W0 两侧的恢复比例中位数是 7.69%–9.52%，最高单条恢复比例出现在小簿，约 53.5%。深簿且 `k` 较小的记录对应更少的恢复比较。若 `k` 接近 `n`，逐项恢复的渐近上界允许代价反转。这些点按负载和 seed 成组，无法单独识别 `k/n` 对端到端时间的因果效应。 [机制图 PDF](evidence/P13/figures/heap-mechanism-pilot.pdf) · [原始双侧分位数](evidence/P11-heap.csv)

## 瓶颈迁移与论文证据映射

| 论文内容 | 当前可支持的表述 | 证据与边界 |
| --- | --- | --- |
| Methods · 堆恢复 | 仍合法的剩余堆接收相同暂取订单，恢复仍使用 PAMS 价时比较。改动的最坏复杂度随 `k` 和 `n` 变化 | 固定 PAMS、A2 最小恢复改动和独立 G1-heap 技术记录。 [HEAP_METHOD](HEAP_METHOD.md) · [G1-heap](../../gates/G1-heap.md) |
| Mechanism · 恢复工作量 | Apple M5 的六对 pilot 显示，金融事件一致时仍可减少恢复段比较器调用，深簿低恢复比例的对照差距更大 | 订单数、状态、RNG、双侧有序记录、比较调用与高比例尾部均保留。正式收益需 H01 完整种子与 V01。 [图表数据](evidence/P13/figures/heap-mechanism-pilot.csv) |
| Pilot · 原版热点与迁移 | W1-H seed 11 中，原版 cProfile 的 heapify 累积约 2.499 s，占剖析总时间 2.903 s。增量后 `Random.sample` 累积约 0.151 s，占该次剖析约 32%。独立阶段诊断的恢复段为 11.498 s → 0.294 s | 每个探针有自身计时边界。cProfile 可包含目标恢复以外的上游 heapify，阶段时间采用恢复专属边界。两套观测各自解释，均不进入正式计时。 [剖析与阶段 raw](evidence/P13/INDEX.md) |
| Pilot · 原生化与包装 | W1-H seed 11 的原生串行分段包含约 0.249 s 的 packing/借用和 0.0009 s 的求值调用。W2-H、W3-START 的低开销 pilot 中，在相同增量堆路径上使用 native-serial 未进一步降时，W4 两个 seed 方向不一 | 保留慢与不确定结果。连续核 replay 使用实际捕获的生产行，观测范围为热输入上的核。正式原生化与多核收益需要各自对照。 [pilot 运行及分段](evidence/P11-runs.csv) · [阶段表](evidence/P11-phases.csv) |
| Results · 端到端、多核和 Cache | 正式估计均待数据。比较器计数支持算法工作量解释 | 硬件层证据需要目标主机上可用且定义正确的事件、对应作用域、有效采样与匹配工作量。当前无 PMU 或缓存模拟读数用于此图。 公共实验与 PMU 协议 (`$COREORDER_LEADER_PACK/CoreOrder_Member_A/common/09_Experiments.md:157`) |

## 版本与责任

- P13 从 G3 候选审查提交 `fef940ec3d9c9ffbed0d7732fd9f8a8243b1b9bb` 建立本地证据分支 `codex/p13-heap-evidence`。生产路径与 `92f8bbf08da514dcb24e27b6a815d3947c352798` 一致，固定 PAMS 为 `6cd53810103780770c5b5d6ee0069ccab9f4b358`，候选工作负载、配对清单和协议均通过 SHA-256 复核。
- P11 raw 运行 checkout 为 `3c344f765c6ff288abad2faa6081c921f0ee0f36`，本地诊断汇报提交为 `1bb8e081e3b7ad348b7807bcd5870e8e22098a36`。本机为 Apple M5、macOS 27.0 arm64，CPython 3.12.11、Apple Clang 21.0.0。P11 和 P12 的本机扩展 SHA 分别为 `06b8437036d4111e105274805d0586774150a2009a75d9080c749f3f23ae0593` 和 `f680634422bfc56d3155498d1d3bb272755843fd2bd407e937bc6c114b615dad`。二者是各自的诊断构建。 [环境回执](../../gates/evidence/P12/mac-environment.json) · [文件核对日志](evidence/P13/audit.txt)
- A/E 收口共同 G2 与 E 记录身份、量测来源和 `validation_run_id`。目标主机负责人提供生产代码、依赖、编译、扩展、环境与可用事件的回执。E 提交 E4 采集及统计入口、V01 回执和正式 raw/分配，A/E 签认生效锁。若前置修复改变受测生产条件，按 G3 规则生成新协议、重新验证受影响条件并重测。 [重测规则](../../gates/G3.md)

## 复现入口

在同一干净生产候选工作树构建 Release，使用本记录中的证据脚本。下列 `/path/to/evidence` 为记录提交的脚本目录。

~~~sh
mkdir -p results/p11-rerun
cp /path/to/evidence/replay_p11.cpp results/p11-rerun/
export PYTHONPATH="$PWD:$PWD/build"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1
.venv/bin/python -B /path/to/evidence/pilot_p11.py results/p11-rerun/runs
.venv/bin/python -B /path/to/evidence/supplement_p11.py results/p11-rerun /path/to/evidence/pilot_p11.py
.venv/bin/python -B /path/to/evidence/summarize_p11.py results/p11-rerun/runs results/p11-rerun/tables
~~~

三个入口分别产生原始运行、删失复跑及 C++ replay、图表数据。工作负载字节校验在日志的 `identity.log` 摘录。
