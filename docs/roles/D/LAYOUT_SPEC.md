# 成员 D 的 R4 布局与热字段审计

契约 `coreorder-r4-v1`。在 Windows x64 编译 A 的 `include/coreorder/contracts.hpp`，确认其与 B 候选实现中的头文件逐字节相同（SHA-256 `b23045f2cd5e329eb672fd070959278ff258a1f3e2f10857bcf1a6502df562b2`）。D 的 `native/layout/abi.hpp` 引入该公共头，并定义与两种布局共用的行身份记录。独立编译时将该头所在的 `include` 加入搜索路径；合入团队仓库后使用组长维护的版本。

## 一行的来源与去向

| AoS 偏移（字节） | 字段（依次排列） | 每批的真实取值与用途 |
|---|---|---|
| 0, 8, 16 | p_now, p_fund, p_then | Market 当前市价、当前基本面价格、在 `t-min(t,window)` 的历史市价。读取两个时间位置，不扫描整个窗口。 |
| 24, 32, 40 | w_f, w_c, w_n | 精确 FCN 实例的 fundamental_weight、chart_weight、noise_weight |
| 48, 56 | noise_scale, order_margin | 同名 agent 属性，按当前值打包 |
| 64, 72 | z_noise, z_margin | A 提供的 agent 原采样；fixed 只消耗一次 gauss，第二列为 +0.0；normal 有第二个原样本 |
| 80, 88, 96 | window, effective_window, mean_reversion | time_window_size、min(market.get_time(), window)、mean_reversion_time |
| 104, 108 | margin_type, chart_sign | fixed=0 / normal=1；is_chart_following 映射 +1 / −1 |
| 输出 0, 8, 12 | price, side, error | B 写入原始价格、方向、错误码；A 按行检查错误后回建，空单价格 +0.0 |
| 元数据 0, 8, 16 | agent_id, market_id, call_index | D 按 A 的调用次序和市场遍历次序写入；A 按调用归组并保留组内顺序 |

源头是 Python 对象属性与 Market 历史序列，内存包含对象头、引用与单独的数值对象；这些对象没有 R4 行记录的天然步长。D 读取可访问 agent–market 对，直接写入选定布局。每行包含 10 个 float64、3 个 int64、2 个 int32，共 112 B。结果是 1 个 float64 和 2 个 int32，共 16 B，身份另占 24 B。三类记录均按 8 B 对齐。模型定义、随机语义和订单构造归 PAMS；D 新增显式的存储布局和身份映射。[固定版 FCNAgent](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/agents/fcn_agent.py) · [Market 的历史价格读取](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/market.py)

## 供 A/B/C 接入

```text
A 的有序 agent 和 simulator.markets，A 的原有随机样本
  → D 的连续 AoS 记录 / 15 个连续 SoA 列 + 同一组行身份
  → B 的 Evaluator.aos(ndarray) / Evaluator.soa(dict)
  → coreorder::evaluate_range(const InputView&, OutputView, size_t begin, size_t end)
  → A 按 call_index 重建非空订单，再使用上游处理函数
```

AoS 只持有一个输入地址，跨行相同字段的步长为 112 B。SoA 持有 15 个列首地址，float64/int64 的步长为 8 B，int32 为 4 B。B 的 binding 在持 GIL 时逐个验证 dtype、端序、有效长度、步长、ALIGNED 标记和实际对齐，直接持有数组引用；AoS 和 SoA 都读取 n 个完整行。B 的 C++ range 分别用 `load_row` 取值，再调用同一 scalar。范围为 [begin,end)，C 仅调度互不重叠的结果下标。禁止 worker 保存 Python 对象，所有 range 结束后才能释放或重用对应批次。绑定只接受实际的 Python dict 用作 SoA 列表。

## 实测与复现

在 VS 2022 x64 开发者命令行，从本仓库根目录运行。示例使用本次只读取得的 A 快照；修改 include 路径即可在完整仓库复验。

```batch
cl /std:c++17 /EHsc /O2 /fp:strict /W4 /WX /I"..\evidence-inputs\A\include" tests\layout\abi_check.cpp /Fo:"%TEMP%\abi_check.obj" /Fe:"%TEMP%\abi_check.exe"
python tests\layout\compare_abi.py "%TEMP%\abi_check.exe"
python benchmarks\layout\windows_hardware.py
wpr -pmcsources
whoami /priv
```

MSVC 19.44.35217、NumPy 2.4.6 与 CPython 3.14.5 通过 21 个字段的偏移、大小、对齐和跨语言读写检验。Python 写出两行不同数值，C++ 逐字段按名读出，验证降序市场身份、相同调用序号，以及超过 32 位宽的整数。这是 ABI 测量，阶段模块的运行时和实际测试另见 STATUS。归档命令输出在 [abi.txt](evidence/abi.txt)。

Windows 11 10.0.26200，AMD64，Intel Core i7-14650HX。Windows 内核返回 1 个处理器组、1 个插槽、16 个物理核、24 个逻辑处理器，可见物理内存 16,790,925,312 B。L1 数据缓存分别为 8 × 32 KiB 和 8 × 48 KiB；L2 为 8 × 2 MiB 和 2 × 4 MiB；L3 为 1 × 30 MiB。所有缓存记录的 line size 均为 64 B。指令缓存和共享逻辑处理器数量见 [hardware.json](evidence/hardware.json)。探针只读取单组系统的 Windows 拓扑与内存 API。[Windows 拓扑 API](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getlogicalprocessorinformation)

当前会话未列出 SeSystemProfilePrivilege 或 SeProfileSingleProcessPrivilege。WPR 成功列出 9 个可同时选择的来源上限以及 TotalCycles、CacheMisses、LLCMisses 等事件；实际 ETW 采集权限为 N/A（未启动记录器），PMU 计数为 NOT_RUN。当前 PATH 中没有 perf 或 valgrind。原始枚举见 [pmu.txt](evidence/pmu.txt)。

## 等量对照与解释范围

两布局都保留 112 B 输入、16 B 输出和 24 B 身份。比较时固定行序、输入位、价格计算、调度、市场和最终轨迹；容量闲置与有效字节分别计数。跨行访问单列可受益于 SoA 连续读，但 FCN 每行读取多个字段，AoS 保留的行内邻近性也可能有利。输入字节数只描述表示，不能替代实际缓存流量、有效带宽或 FLOP 测量。Linux perf 需记录 PMU 名与计数范围；Cachegrind 的缓存数据属于模拟。两者的测量与系统性能归因均待统一实验协议。[Intel 布局变换](https://www.intel.com/content/www/us/en/developer/articles/technical/memory-layout-transformations.html) · [Roofline 原始报告](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2008/EECS-2008-134.html) · [perf stat 手册](https://man7.org/linux/man-pages/man1/perf-stat.1.html) · [Cachegrind 手册](https://valgrind.org/docs/manual/cg-manual.html)
