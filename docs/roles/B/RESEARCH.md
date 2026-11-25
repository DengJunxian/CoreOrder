# B1 至 B3 研究记录

以锁定版本的 PAMS 和分发包中的 `common/05_Technical_Contract.md` 为准。金融策略、市场、订单构造与随机过程沿用上游。`tests/native/b1/fcn_probe.cpp` 与分发包 `common/evidence/native_fcn_probe/fcn_probe.cpp` 逐字节相同，诊断目录保留 PAMS 原始 EPL-1.0 文本。B1 探针通过固定版本 pybind11 和 Taskflow 编译，两者继续按上游 BSD-3-Clause 和 MIT 许可使用。B2/B3 按候选仓库的依赖锁和上游许可编译。

独立参考入口 `tests/native/b1/oracle.py` 直接调用固定源码的 `FCNAgent.submit_orders_by_market` 并提取未入簿订单字段。B1 在真实 Market 对象中构造市场历史，抽样对照使用独立的 Python `Random` 实例。检查每次调用的完整 PRNG 状态和 `gauss` 调用次数。观察用 `Random` 子类只统计调用并委派原实现。数值核接受 Python 抽样后的值。ABI 验证使用单独的 C++ 类型和 NumPy 对齐 dtype，逐项比较大小、偏移、对齐和行 stride。

B2 以 G0 候选的实际 C++ 头与 NumPy dtype 实现一个标量和两个 view 的区间遍历。主要研究变量是表达式操作顺序。把 `(1.0 / weight) * value` 重写为除法，或打开浮点重结合与乘加收缩，都可能改变最后一位。B3 的绑定只借用已校验的 NumPy 输入，输出按 ABI 分配。准备高斯数、打包和金融对象回填由上游与 A/D 路径负责。

首轮验证发现两个问题。NumPy 可将单行或空的结构体字段切片标成连续，但实际 stride 仍是 112。正式绑定依契约拒绝该 stride，测试打包改为生成真正紧密的列。另一项是跨主机高斯重新抽样的两条末位差异，候选数据来自 macOS ARM64，本机为 Windows 下的 WSL2 x86-64。Python `Random.gauss` 使用本机数学库，故相同 MT 状态不承诺高斯浮点值跨主机逐位一致。现有数据无法进一步区分 libm 或构建差异。公共 fixture 按已捕获的随机数回放，同机差分仍逐值核对 Gaussian 值、cache 和完整状态。具体输入身份和浮点 hex 保留在日志。

模块诊断微基准用同一真实公共数值输入切片平铺，测量直接串行绑定调用，并交替两布局次序。结果包含缓冲校验、输出分配、数值计算、错误扫描。其外推范围限于本机模块接口路径，正式端到端计时另由 E 按冻结计划采集。

依据来源

- 固定 PAMS 的 [FCN 实现](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/agents/fcn_agent.py)、[订单](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/order.py) 和 [市场](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/market.py)。
- Hirano、Takata 和 Izumi 的平台预印本介绍 PAMS 的设计与使用案例。具体运行语义以固定源码为准。[PAMS 论文](https://arxiv.org/abs/2309.10729)
- 浮点操作顺序及目标格式影响舍入。编译使用 `-O3 -fno-fast-math -ffp-contract=off`，`log/exp` 的逐位结果在目标环境验证。[IEEE 754-2019](https://standards.ieee.org/ieee/754/6210/)、[GCC 编译选项](https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html)
- pybind11 对 GIL、缓冲 dtype 和 stride 的说明以 v2.13.6 固定文档为准。[GIL](https://github.com/pybind/pybind11/blob/a2e59f0e7065404b44dfe92a28aca47ba1378dc4/docs/advanced/misc.rst#global-interpreter-lock-gil)、[NumPy](https://github.com/pybind/pybind11/blob/a2e59f0e7065404b44dfe92a28aca47ba1378dc4/docs/advanced/pycpp/numpy.rst)
