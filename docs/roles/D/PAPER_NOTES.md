# 数据布局与转换成本 · 论文方法素材

## 可写入方法章节

我们将 FCN 决策的一行定义为一次可访问的 agent–market 调用，并在 Python 层按上游的 agent 调用顺序和模拟器市场顺序生成缓冲区。固定比例下单模式使用一个高斯样本，正态下单模式使用两个。随机数的产生留在原 agent 决策时间线，布局层只读取样本。每批重新采集当前字段，因此事件修改窗口、价格或策略参数后能够在下一批生效。记录独立的 agent ID、market ID 与调用序号支持按原组回填。[原 FCN 决策路径](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/pams/agents/fcn_agent.py#L114-L237)

参与比较的 AoS 与 SoA 均由十个 float64、三个 int64 和两个 int32 字段构成，每行有效输入 112 B。AoS 将同一行字段相邻存放；SoA 为每种字段保留一个连续列。条件分支可能跳过部分字段，但两个实验条件始终提供相同的数值输入、输出格式和决策行次序。这样，字段裁剪、人工填充以及提前合并策略系数不会改变对照条件。C++ `sizeof/offsetof/alignof`、NumPy dtype、实际地址、步长和跨布局逐字段往返共同验证 ABI。内核结果占 16 B；后台容量、有效行与元数据单列统计。

## 结果该怎样解释

将 A 的 draw/pack、B/C 的 native compute 和 A 的 rebuild 分开计时，另测包含完整转换路径的耗时。仅压缩表的生成更快可以支持“该生成路径在本机更快”，尚不足以归因于末级缓存。缓存行能容纳的连续同字段元素数取决于实测缓存行宽及字段宽度，AoS 的行字段集中也可能有益于 FCN 的多字段标量访问。二者的净效果须在冻结的工作负载、编译器及同一公式下检验。论文中保留相同工作量、各计时边界和可观测限制。[Intel 布局变换](https://www.intel.com/content/www/us/en/developer/articles/technical/memory-layout-transformations.html)

## 两页答辩底稿

1. **一行装了什么？** 从市场当前时刻沿价格历史回溯 `effective_window`，预测期单独保留 `window`。在白板上画两行相邻 AoS 和两列相邻 SoA，标出 `p_now` 横跨两行分别相距 112 B 和 8 B。演示稀疏访问时为何第二个可见 agent 的调用序号可能跨过空 agent。
2. **如何判断值得打包？** 并列展示本机实测的缓冲字节、读取范围和 pack 微基准，再说明完整运行还会经过计算、重建及上游订单处理。展示事件变更前后同一槽位的输入与完整 RNG 状态校验。正式端到端速度、PMU 事件与跨 worker 一致性均由组长统一验收后补入。
