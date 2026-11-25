# 成员 A 论文记录

## P01 平台与复现

Methods 记录 PAMS 固定提交和 EPL-1.0 来源，金融平台归属上游。Taskflow 和 pybind11 的固定版本与许可列在复现清单，编译配置以实际 Release 命令为准。

P01 结果支持本机基础工具链可重建。金融轨迹、堆恢复、原生 FCN、布局与性能结论等待对应阶段的实际验证和测量。

## P02 串行参考和语义继承

Methods 可引用固定 PAMS 的 `SequentialRunner` 及官方 CI2002 配置作为串行基准。CoreOrder 的 P02 贡献是可追溯运行入口、原配置和独立调用 reference，业务公式、激活与下单规则、订单簿、撮合、账户和事件继续由 PAMS 驱动。

诊断核验中，官方 600 步的价格记录与直接 reference 相同。24 代理的同 seed smoke 在 `py-seq` 两次运行及 reference 中给出一致的有序交易和终态。时长包含观察器开销，正式实验需另用冻结的对照与计时边界。
