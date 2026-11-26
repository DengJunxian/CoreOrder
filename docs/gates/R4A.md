# R4A · 华硕 x86 主机资格与实验前 pilot

**2026-11-26（上海时间） · x86 构建及代表正确性 PASS · 正式矩阵 BLOCKED**

华硕天选 Air 2025 可在现有 WSL2 环境构建并执行 CoreOrder。完整验证的内存和墙钟成本是本轮发现的主要准入阻断。P01 使用 seed 11、29，单独保留记录。G3 和冻结候选清单维持原状态，正式 seed、C01/V01 批次及正式 E01–E05 未运行。

## 主机、Cache 和控制变量

| 项目 | 实测结果 |
| --- | --- |
| 设备、系统 | Windows CIM 报告 ASUSTeK `TX Air FA401KM_FA401KM`、Windows 11 build 26200。来宾为 Ubuntu 24.04.5 LTS，内核 `6.18.33.2-microsoft-standard-WSL2`，x86-64。 |
| CPU 与线程 | Windows 和 WSL2 均报告 AMD Ryzen AI 7 H 350 w/ Radeon 860M，8 核 16 线程。来宾 CPUID 为 Family 1Ah、Model 60h、Stepping 0，1 socket、1 NUMA node，SMT active。 |
| 微架构 | AMD Family 1Ah Model 60h 属于 Krackan 系列。AMD 公布的 Ryzen AI 7 350 为 4 Zen 5 + 4 Zen 5c。主机品牌字符串带 H 后缀，Windows CPU Set 实测两个 EfficiencyClass，class 1 对应 Windows CPU 0–1、4–5、8–9、12–13，class 0 对应 2–3、6–7、10–11、14–15。每类 4 个物理核心，符合规格所述的异构结构。WSL2 16 个 CPU 的最高扩展 CPUID 均为 `0x80000021`，未暴露可识别 AMD 异构类型的 `0x80000026` 叶。 |
| L1I / L1D | 每个来宾核心 32 KiB 指令 Cache、48 KiB 数据 Cache，共 8 组。每个实例由其两个来宾 SMT sibling 共享。 |
| L2 | 每核心 1 MiB，共 8 组。每个实例由其两个来宾 SMT sibling 共享。 |
| L3 | 16 MiB 单一实例，由来宾 CPU 0–15 共享。实测 4 级 Cache 的一致性行长度均为 64 B。 |
| 内存 | Windows CIM 报告 33,413,771,264 B 可见物理内存。来宾约 15.18 GiB，4 GiB swap。 |
| 测量环境 | WSL2 可见 CPU 0–15。P01 所有独立子进程继承固定掩码 `0,2,4,6,8,10,12,14`，每个来宾核心取一个 sibling。验证和配对均在同一主机和来宾内进行，所有变体使用同一掩码。Windows 的物理 CPU 调度与来宾 CPU 编号之间未建立映射。 |
| 供电与频率 | WSL2 看到 AC 在线、电池已满，Windows 当前电源计划为 Silent。WSL2 每个 vCPU 的 `lscpu` 频率读数均为 1996.203 MHz，来宾无 cpufreq policy 与 CPU 温度传感器。该读数只作为来宾报告值归档。 |

Cache 共享关系按来宾 sysfs 记录。AMD 的 [Krackan 系列资料](https://docs.amd.com/r/en-US/xapp1377-heatsinks-thermal/x86-TDP-Thermal-Models-Package-Files-and-Pressure-Specifications) 和 [Ryzen AI 7 350 规格](https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-7-350.html) 给出型号族背景。CPU Set 的 EfficiencyClass 定义来自 [Microsoft 文档](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-system_cpu_set_information)，CPUID 叶定义参见 [Linux x86 拓扑文档](https://docs.kernel.org/arch/x86/topology.html)。

单独使用 W3 8-worker cProfile 负载做主机观测，连续 12 个 Windows 样本中有 8 个时间戳落在命令内。该区间 Hyper-V 主机逻辑处理器 `_Total` 忙时 26–41%，ACPI 热区 `_TZ.TZ01` 为 355–356 K（约 82–83°C），`PercentPassiveLimit=100`、`ThrottleReasons=0`。这是热区和短时负载观测。CPU 封装 Tctl 缺测，CIM 频率固定显示 2000 MHz，Hyper-V 频率字段为空，无法判断长时间高负载下的物理核心降频。原始温度单位和 throttling 字段见 [Microsoft thermal counters](https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/examples--requirements-and-diagnostics)。正式候选先保留 workers 1/2/4，8 是增强点。4 和 8 workers 在 W3 跑通，2 workers 有封存小场景回执。今后若继续用 WSL2，采集前后记录 AC 和同一电源计划，并记录来宾与 Windows 背景负载，每次只运行一个实验子进程。采用同一线程限制，OMP、OpenBLAS、MKL、BLIS、NumExpr 和 VECLIB 均设为 1。来宾掩码只保证来宾线程的可调度范围，高负载期间的主机温度与降频另报证据。

[Linux 环境](evidence/R4A/host-linux.log) · [Windows 主机环境](evidence/R4A/host-windows-encoded.log) · [CPUID 实测](evidence/R4A/cpuid.log) · [P01 环境和逐条记录](evidence/R4A/chronological.jsonl) · [观测命令](evidence/R4A/host-under-load.log) · [热区和负载采样](evidence/R4A/host-under-load.jsonl)

## 锁定构建和正确性

测量源码为 R3 的 `b5808b5383bfc170fcb972ee77f1c3c0eac5659f`。在目标机通过本地 Git bundle 建立干净 checkout。GitHub 公共候选仍为 `8f25a381f08ea9c398b6835c64ea470918819451`。三个 upstream gitlink 与候选一致，PAMS `6cd53810103780770c5b5d6ee0069ccab9f4b358`、Taskflow `816b4ad53b44196c88f409eb7b4a25a0e3bfdf42`、pybind11 `a2e59f0e7065404b44dfe92a28aca47ba1378dc4`。

CPython 3.12.3 新建 venv，安装 `requirements.lock` 和本地 PAMS 0.3.0，`pip check` 退出 0。GCC 13.3.0 和 CMake 3.31.6 完成 Release 构建。三个生产扩展翻译单元的实际命令均含 `-O3 -DNDEBUG -fno-fast-math -ffp-contract=off`。被运行记录加载的扩展为 `source/build/_coreorder_fcn.cpython-312-x86_64-linux-gnu.so`，SHA-256 `a246234c5f604fd97789af5ac8c24abfeb4a104b29683f80db97a8b76f735366`。根 CTest 7/7，x86 E1 smoke PASS。

C01b 的独立 PAMS oracle 在同一目标机运行。seed 11 上，py-process 4、direct native 两布局、Taskflow 4 两布局的逐语义比较均通过。封存链路另外保存 seed 11、29 × direct/native-parallel 2 workers 的 4 份开发验证回执。24 条 timing 的同字节配置、同 seed 对照形成 7 组，金融事件计数、市场步、终态与最终 RNG 摘要均一致。同主机独立 oracle 才用于正式语义签认。

[远程 ref](evidence/R4A/remote-refs.txt) · [实际构建日志](evidence/R4A/build.log) · [实际编译命令](evidence/R4A/compile_commands.json) · [开发回执](evidence/R4A/receipts/) · [小规模封存链路日志](evidence/R4A/sealed-pilot.log)

## P01 完整仿真测量

`simulation_s` 为生产低开销路径的业务时间。全进程秒包括加载、启动至退出，并涵盖计时外的终态和 RNG 输出。每行表示该负载本次实际采样范围，保留慢点。实验顺序、完整设置、运行 ID、配置哈希、健康读数、时间和大小详见 raw 索引。P01 主驱动记录 38 条尝试及 603.7 s 墙钟，另有 1 次显式输入捕获和 8 个 replay 作为失败后的替代诊断。

| 候选或对照 | seed | 成功 timing 数 | simulation_s | process_wall_s | raw/次 |
| --- | ---: | ---: | ---: | ---: | ---: |
| W0-CI2002 | 11, 29 | 6 | 0.041–6.936 | 0.320–7.221 | 0.89 MB |
| W0-H（增量，py-seq） | 11 | 1 | 0.033 | 0.305 | 0.89 MB |
| W1-H | 11 | 2 | 0.213–1.204 | 0.920–1.916 | 31.85 MB |
| W2-H | 11 | 2 | 0.308–5.230 | 1.033–5.965 | 32.03 MB |
| W1-SMALL-BATCH | 11 | 4 | 1.767–1.906 | 2.462–2.623 | 31.91 MB |
| W2-MEDIUM-BATCH | 29 | 4 | 2.029–2.326 | 2.821–3.116 | 32.91 MB |
| W3-LARGE-MULTI | 11 | 5 | 1.634–2.037 | 4.464–4.749 | 128.57 MB |

W0 的 `py-process/spawn` 慢点为 6.936 s，保留在 E01 成本评估中。独立 C01b 诊断向子进程提交 21 个任务，父调用队列序列化发送 1,048,323 B，管道发送累计 0.131 s。后者只覆盖父进程 send，整体开销另见 W0 进程墙钟。W1/W2 在相同初始工作量下可见原生化的负收益或小差异。W3 的 4/8 workers 与 AoS/SoA 差异很小，建模与 RNG 准备、调度和打包影响须通过独立阶段诊断解释。W1/W2 堆对照测得业务时间差异，正式效应和波动留待五 seed 配对。

P01 的外层驱动曾在 W0 `py-process` 子运行进行时停止，以撤除一个超出 24 条上限的尚未启动配置。已启动子运行保留其自身完整回执，外层退出码及外层 elapsed 缺失。后续启动 W3 8-worker 的参数位置错误发生于 `Popen` 之前，修正后续跑，头一次失败保留在控制台。Bash 层串行和所有运行 ID 均保留，现有 raw 未覆盖。

[计时与比较记录](evidence/R4A/chronological.jsonl) · [完整控制台](evidence/R4A/pilot-console.log)

## 完整验证和 8 小时预算

原清单含 C01 420 条、V01 170 条、timing 527 条（预热 62）和 E05 最多 108 条。按候选工作负载和设置对应 P01 最大外层 elapsed。136 条没有同设置 pilot 的 timing 行使用同工作负载内的最大观测值。W0 `py-process` 的外层 elapsed 以自身 7.221 s 子进程时长加 0.275 s 的实测最大外层差额估算。以下是资源规划，覆盖当前 runlist 的重复、预热与真实的摘要成本。测量间冷却、额外重试、正式 seed 差异与未来来宾调度仍需留余量。

| 阶段 | 原预算 | 估计及可行性 |
| --- | ---: | --- |
| C01 | 40 min | 仅依据 C01b 独立 oracle 0.327 s、最慢代表对照 0.972 s，60 个 oracle 加 360 个候选约 6.16 min。其余 11 个正式 C01 场景未测，估计不能代替准入。 |
| V01 | 80 min | 现行完整实现无法完成本次候选形状。W0 oracle 92.18 s、418 MB，候选同时保留状态及解码参考，在 7 GiB 虚拟地址上限下的比较阶段退出 1。W1、W2、W3 在独立 oracle 阶段触及上限并退出 1，耗时分别为 78.01、89.59、101.33 s。对应候选比较未启动。 |
| E01/H01/E02/E03 | 275 min | 527 条投影约 30.79 min，分项约 4.77/3.40/13.20/9.43 min。按同负载最大样本 raw 投影为 29.63 GB。 |
| E05 | 35 min | 硬件计数、函数与阶段诊断、真实输入 replay 分开采集。保留各子项上限，以合格事件组和可验证诊断输入确定编排。 |

W0 失败记录中的业务 `status=PASS` 对应已完成的仿真，外层退出码为 1，`validation_status=NOT_RUN`。正式准入需要独立差分回执。失败留在预算中。使用相同原始轨迹另启比较进程，W0 的事件、逐步状态、终态、RNG 和初态全部通过。离线比较 62.96 s，峰值常驻内存 8.02 GiB，进程上限 10 GiB。仅以这次观测到的 oracle、候选尝试与离线比较成本外推 W0 的 5 个 oracle 和 30 个候选，约需 90.2 min。当前消耗瓶颈是完整状态轨迹在采集、编码和同进程解码中的驻留量。可在后续实现逐步流式写入与比较，按原 oracle 逐事件、逐步状态、完整 RNG 作等价验收。分阶段计时后重新估算全部 retained rows。单次操作能完成才有意义，当前无法签认 480 min 内完成冻结矩阵。

负载建议以完整验证能力及原定 2–10 s 业务时间为准。保留 W0 和两种原有堆恢复配置。维持 E04/W4 关闭，先移除额外 8-worker 点。W1 和 W2 接近或落在目标时间，继续作为核心候选。若 W3 完整等价验证仍不可行，按规范对全部比较条件统一调节 W3 尺寸并生成新 ID、配置摘要和候选清单。正式纳入的所有条件仍需五 seed V01。排除或缩减使用可验证处理成本与预定资源边界。

[预算计算](evidence/R4A/budget.json) · [计算脚本](evidence/R4A/budget.py) · [失败日志](evidence/R4A/validation-failures/) · [W0 离线比较](evidence/R4A/w0-offline-compare.log) · [冻结候选清单](../../configs/experiments/frozen.json)

## PMU 能力与 Cache 机制证据

目标来宾 `perf_event_paranoid=2`。直接用 `perf_event_open` 在 guest CPU 0 对当前线程的 user-space 工作量逐项探测。Windows/WSL 环境保持原配置。随后从 Ubuntu 签名包索引下载并解包用户态 perf 6.8.0 到实验目录，在 W2-H seed 11 上经生产 `--mode pmu` 试采 native-serial 与 native-parallel 4。该阶段按事件组分开运行。采集范围覆盖 Python worker 及继承的任务，含导入、初始化、仿真和摘要。原始计数未缩放。

| 事件或组 | 状态 | 现场观察与解释 |
| --- | --- | --- |
| `cycles:u`、`instructions:u` | **PASS** | 直接探针为正，生产两个运行均为正，运行覆盖均报告 100.00%。目标 AMD 内核映射为 `0x0076`、`0x00c0`。 |
| `branches:u`、`branch-misses:u` | **PASS** | 直接探针为正，生产两个运行均为正、100.00%。分别为退休分支和退休误预测，内核映射 `0x00c2`、`0x00c3`。 |
| `L1-dcache-loads:u`、`L1-dcache-load-misses:u` | **PASS** | 直接探针为正。生产计数均为正、100.00%。运行内核对这个 AMD 系列映射到 `0x0040`（Data Cache Accesses）和 `0xc860`（L1D miss 导致的 L2 访问）。按这两个事件各自的定义解释；perf 自动列出的百分比不足以证明标量 load 指令的缺失率。 |
| `LLC-loads:u`、`LLC-load-misses:u` | **BLOCKED** | 直接 syscall 的两个末级事件均返回 `ENOENT`。生产 perf 两种执行均返回 `<not supported>`、runtime 0，PMU 收集退出 1。缺测。 |
| generic `cache-misses` | **PASS（探针）** | 单线程计数为正。当前 AMD 内核映射与专用 LLC 事件不同，正式 LLC 列保持缺测。 |
| `task-clock` | **PASS（探针）** | 软件时钟阳性对照，同一调用线程。 |

正计数、启用/运行时间与 scope 三者一起核查，不能仅据 perf 打印的百分比接纳样本。事件映射依据目标内核同版本 [WSL2 AMD perf 源码](https://github.com/microsoft/WSL2-Linux-Kernel/blob/linux-msft-wsl-6.18.33.2/arch/x86/events/amd/core.c#L128) 及 [Linux perf_event_open 文档](https://www.kernel.org/pub/linux/docs/man-pages/book/man-pages-6.13.pdf)。已合格的三组可作为 E05 候选；正式采集仍须每次检验有限、有效、覆盖率达标的计数和运行身份。

原生阶段 profile 和首轮 P11 行捕获保留为失败。R3 在目标的 CPython 3.12.3 上，观察到 6 次同一真实绑定对象的 `c_return`、0 次匹配的 `c_call`，阶段完整性检查因此拒绝该记录。W3 的生产函数级 `--cprofile` 通过。另用显式包装记录同一真实生产绑定的输入并正常调用，未更换数值核。W2-H seed 11 捕获 8192 个原序 AoS 输入行，单输入 112 B、单输出 16 B。四个预设前缀为 128、512、2048、8192 行，名义输入加单输出工作集依次为 16、64、256 KiB 和 1 MiB。AoS/SoA 的输出 SHA 在每个前缀逐字节相同。8 个 replay 的核与 binding 时间为 0.060–0.146 s，驱动时长为 0.268–0.343 s。SoA 输入拆列在 replay 计时之外。

本次 replay 跨过名义 L1D 容量并到达 L2 容量量级。工作集、布局和可用 L1D 事件可用于受限的访存分析。当前 8192 行低于 16 MiB LLC，无法据此判断 LLC 容量拐点或因果归因。预留 E05 的 profile 4 min、replay 10 min 与 setup 9 min。CPU/branch/L1 三组保留 12 min PMU 上限。以现有路径估算单次 replay 有足够裕量，后续按原计划将两布局共享的调用次数校准到约 0.2–1 s，再验证 parallel 配置与冻结源输入。原生阶段拆分仍需修复并做目标机回归，正式报告保留可用函数诊断与硬件计数范围。

[直接系统调用](evidence/R4A/pmu.log) · [用户态 perf 下载、验证和运行](evidence/R4A/pmu-core.log) · [实际 perf CSV 和回执](evidence/R4A/pmu/) · [阶段事件复现](evidence/R4A/profile-events-retry.log) · [生产行源](evidence/R4A/replay-source.json) · [Replay raw](evidence/R4A/replay-summary.json)

## 状态与交接

| 验收项 | 状态 |
| --- | --- |
| 华硕实际环境、Windows 核心分组、WSL 拓扑与固定掩码 | **PASS** |
| 固定版本 Release、实载扩展、7 项 CTest、x86 独立 smoke 与代表回执 | **PASS** |
| P01 24 次独立启动的低开销候选运行、真实行替代 replay、函数剖析和三个可用 PMU 组 | **PASS** |
| W0 完整轨迹离线比较 | **PASS** |
| 当前验证模式的 W0 同进程比较、W1/W2/W3 完整 oracle、x86 原生阶段 profile | **FAIL** |
| V01 80 min 准入、LLC 专用计数、CPU 封装温度与持续降频实证 | **BLOCKED** |
| 全量目标机 C01/V01、G3 激活、E01–E05 正式原始数据 | **NOT_RUN** |

后续阶段输入为经复验的全轨迹流式实现及预算、冻结前确认的 workers/候选配置、正式采集的固定主机控制记录和剩余 G2 签认。按同一目标机重新验证受影响记录和正式矩阵。当前清单由 `experiments.run --stage check` 确认为 `G3 BLOCKED`。

[复跑命令与归档说明](evidence/R4A/README.md) · [完整 raw 远端路径、大小和哈希索引](evidence/R4A/artifacts.jsonl) · [协议检查](evidence/R4A/plan-check.log)
