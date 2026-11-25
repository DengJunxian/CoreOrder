# 第1页：如何知道模型没有被改动

贡献：固定源码oracle、写入时事件收集、完整step/RNG结构比较、首差异与一条重放命令。PAMS承担所有金融策略、撮合和账本；E不重写金融oracle。

现场材料：`results/counterexamples/E2/missing-gauss`。实际漏掉一次高斯采样，订单事件保持相同，但逐step Random状态发生分歧；说明同seed、最终资产或价格图都不足以证明路径一致。

展示顺序：固定PAMS SHA → 原事件顺序 → 逻辑簿/float.hex → Python gauss cache + NumPy state → 首差异路径。解释内部heap数组可以不同，成交先后不能排序消除。

已完成证据：120次上游seq/thread真实回归、上游process代表运行、31项模块测试。生产G2仍INTEGRATION_PENDING，不能说完整原生系统通过。

口述重点：hash是索引，仍展开结构；schema拒绝缺SHA/状态和无来源填零；测试故障明确标识，不冒充生产实现。

---

# 第2页：什么证据才支持性能主张

计时分三个边界：全进程、完整仿真、数值核。完整仿真必须含随机准备、packing、对象重建及撮合。全trace、cProfile、低开销计时分开，最终摘要在计时段外。

五seed×三repeat：五个市场样本，三次机器计时重复；按预定区组配对，再按seed汇总。TIMEOUT保留右删失；null写原因；requested/effective不相等的后备不能算native样本。没有PMU不能声称LLC下降。

本轮展示的是验证工具成本微基准，46事件/7检查点/7次技术重复，绝不转成系统加速倍数。正式性能计划仍NOT_RUN/runnable=false，等待G3冻结。

答辩边界：缺A–D生产模块时独立工具可先交付；真实系统集成、跨ISA、PMU和正式确认性数据由后续任务完成。已实现的无收益和未实现不是同一种结果。
