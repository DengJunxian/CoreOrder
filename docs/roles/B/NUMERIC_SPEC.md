# FCN 数值语义与接口交接

契约 `coreorder-r4-v1`。本文记录固定 PAMS 策略的纯数值提取和内存布局。A 维护公共头文件和市场接入，B 实现标量核及绑定，C 调用同一范围函数，D 提供输入布局。

## 上游行为

引用 `masanorihirano/pams@6cd53810103780770c5b5d6ee0069ccab9f4b358` 的 `FCNAgent.submit_orders`、`submit_orders_by_market`、`Order.__init__` 和 `Market._add_order`。`pams/agents/fcn_agent.py` 的 SHA-256 为 `e8b6d9b642042c0de25099ca41691923463c17a09e231c6c47ce1312ce825922`。

| 分支或边界 | 上游行为和提取要求 |
| --- | --- |
| 市场访问与调用顺序 | 上游逐个处理传入市场。无访问权限立即返回空表，连读取市场时间和抽样都跳过。A 保留原市场顺序，仅打包可访问行。 |
| 时间与窗口 | `effective_window = min(time, window)`，历史价取 `time - effective_window`。`time=0` 时历史价就是现价，即使配置窗口大于 0。预测指数和 TTL 始终使用配置 `window`。配置窗口为 0 时，有效有限计算的预测价等于现价，不创建 TTL 为 0 的订单，仍依 margin 分支执行抽样。 |
| 基本面与均值回归 | 先算 `1.0 / max(mean_reversion, 1)`，再乘 `log(p_fund / p_now)`。均值回归参数为 0 时分母为 1。配置未给 `meanReversionTime` 时，上游 `setup` 使用配置窗口。 |
| 趋势方向 | 先算 `1.0 / max(effective_window, 1)`，再乘 `log(p_now / p_then)`。趋势项乘权重后，顺势乘 `+1`，逆势乘 `-1`。 |
| 噪声 | 可访问调用按原顺序取同一 agent 的 `gauss(0.0, 1.0)`，然后乘 `noise_scale`。`noise_scale=0` 也照常取样。 |
| 预测 | 权重分母为 `(w_f + w_c) + w_n`。分子为 `((w_f * fundamental_return) + ((w_c * chart_return) * chart_sign)) + (w_n * noise_return)`。先取分母倒数再乘分子，现价乘 `exp(expected_return * window)` 得到预测价。 |
| Fixed margin | `0 <= margin <= 1`。只用一次高斯抽样。预测价大于现价则买，订单价是 `prediction * (1 - margin)`。小于则卖，订单价是 `prediction * (1 + margin)`。相等时无订单。 |
| Normal margin | `margin >= 0`。噪声之后用同一 PRNG 取第二次高斯值，订单价为 `prediction + z_margin * margin`，并检查价格非负。方向仍依据预测价与现价比较。即使 `margin=0` 或方向为空，第二次调用也发生。 |
| 高斯缓存 | 上游 `Random.getstate()` 含 `gauss_next`。缓存命中仍计一次 `gauss` 调用，底层均匀随机状态可能不动，因此每次调用须比较完整状态和实际调用次数。 |
| 订单回填 | 有单时以原 agent/market 标识、`LIMIT_ORDER`、数量 1、原始价格和配置窗口构造 `Order`。初始 `placed_at` 与 `order_id` 均为 `None`。Fixed margin 为 1 的买单可以产生零价并触发上游警告，不能拿价格零判断有没有订单。 |
| Tick 取整 | `Market._add_order` 在订单实际入簿时处理 tick，买单向下、卖单向上，并由原版判定已在 tick 上的价格。B 的输出仍为订单原始价格。 |

成功域要保持 binary64 的运算顺序，使用 `std::log` 与 `std::exp` 对应原版调用。禁用 fast-math、浮点重结合和 FMA 收缩。`float.hex()` 比较订单价格，无单价格规范为 `+0.0`。目标环境变化后重新做严格差分。

上游的域断言分布在抽样前后。B2 生产核显式拒绝非有限数值、无效的对数比例、零权重和、非法窗口关系、未知 margin/tag 以及非法 margin。Normal 的候选价即使无单也要检查。同一行存在多种错误时，以实现的检查顺序返回一个 R4 错误码。B3 绑定恢复 GIL 后报告最早的失败行。失败批次不进入性能数据，异常触发前的系统随机状态由 A/E 集成时确认。

## 公共 ABI 与接入

沿用现有字段与偏移。输入按十个 `float64`、三个 `int64`、两个 `int32` 顺序排列，大小 112 字节、对齐 8 字节。输出 `price:float64`、`side:int32`、`error:int32`，偏移 `0,8,12`，大小 16 字节、对齐 8 字节。所有实测偏移见 `evidence/abi.json`。

- `side` 为 `-1/0/+1`。`error=0` 表示成功。发生错误时由调用方检查错误字段以及首个错误行，不能据 `side=0` 当作有效空单。
- `window` 与 `effective_window` 都保留。行外 metadata 维持市场、agent 和原始调用顺序。`window=0` 的最小有效示例可设价格为 `100/100/100`、权重 `1/0/0`、`mean_reversion=0`、normal margin 为 0，两次随机输入使用 fixture 的真实抽样，结果是无单和规范的 `+0.0`。
- `evaluate_range(input_view, output_view, begin, end)` 使用半开区间。D 提供稳定且按契约对齐的缓冲。实现采用 G0 候选 `contracts.hpp` 中的 `InputView` 和 `OutputView`，AoS 与 SoA 共用同一标量公式。
- 绑定持有 GIL 校验 dtype、形状、stride、本机字节序、NumPy ALIGNED 与实际指针对齐，取得 buffer 和 owner。释放 GIL 后只读数值输入并写独占输出槽。计算完成并重新持有 GIL 后，绑定报告错误，调用方用原版 `Order` 回填成功结果。绑定保留 owner，调用方保持数据不变。

本地 C++ 与 NumPy 表示检查使用 A 的候选头、dtype 和真实公开 fixture，D 可用同一脚本独立复核。B1 的实际探针输入为 `N×16 double`，保留在独立诊断路径。B2/B3 使用正式 112/16 字节 ABI。 [生产接入与验收步骤](INTEGRATION.md)
