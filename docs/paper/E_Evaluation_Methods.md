# 独立验证与可信证据方法（E1–E3素材）

以PAMS固定commit为参考语义，全部策略、订单处理和账本保持上游实现。观察器在原日志写入时编码事件，并在完整市场时间推进后保存状态，防止延迟日志与可变引用造成伪一致。逻辑簿使用原比较器，事件数组保留发生顺序；浮点以可逆hex表示。随机核验包含各owner的Python Random完整状态及fundamentals NumPy Generator状态，特别保留gauss缓存。结构首差异与可重放配置随证据提供，SHA256只作检索索引。[固定PAMS源码](https://github.com/masanorihirano/pams/tree/6cd53810103780770c5b5d6ee0069ccab9f4b358)

验证器的故障测试分别交换事件、改变价格一位及漏采一次normal gauss。最后一种在全空订单场景保持事件序列相同，却由逐step随机状态检测出来。无费总现金使用绝对1e-7与相对1e-12的辅助守恒容差，证券数量严格一致；成交事件另重放账户与订单剩余量。该容差不用于放宽路径比较，负现金余额保留上游行为。

实验模板依据公共R4预先固定seed层级、技术重复、区组、超时与缺测规则。区分不确定性层级的依据见[Kalibera–Jones](https://kar.kent.ac.uk/33611/)；具体五seed和配对log-ratio方案为团队协议选择，不声称该文直接规定本项目次数。计时与profiling分离，任何真实PMU计数须保留scope/有效运行比例；[perf stat](https://man7.org/linux/man-pages/man1/perf-stat.1.html)与[Cachegrind官方手册](https://valgrind.org/docs/manual/cg-manual.html)分别约束硬件与模拟证据。当前未采PMU或正式系统性能数据。

当前可核验范围是E模块与固定上游回归：120个seq/thread短运行、独立process代表运行和已知故障定位。A–D生产模块未交付时不签G2，跨ISA/libm与扩展策略不外推。原生化、堆恢复、多核、布局的系统收益须在后续真实集成和G3冻结后研究。本节不预填任何正式性能主张。
