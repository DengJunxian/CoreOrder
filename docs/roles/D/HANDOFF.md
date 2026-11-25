# 成员 D 接入说明

适用契约 `coreorder-r4-v1`。每个 run 建立一个 `LayoutBuffer(layout)`，每批从当前 PAMS agent 与 Market 写入。A 按原版顺序选择 agent、消耗高斯样本、回建并提交订单。B 的正式串行 Evaluator 已在 Windows x64 测试。

## Python 接口

`pack_batch(buffer, agents, markets, samples, *, first_call=0, market_adapter=None)` 返回上下文管理器。A 在 simulator 状态稳定期间进入上下文。agents 是受剩余非空订单列表名额约束的有序批次，markets 是 simulator.markets，samples 是按可访问 pair 顺序排列的序列。fixed 使用 `Draw(agent_id, market_id, z_noise)`，normal 还要传入第四个参数 `z_margin`。一个有权访问但最终无单的 pair 仍需要样本。未知副作用的 agent 会被拒绝。已由 A/E 审核的等价市场子类由 A 以确切类传给 market_adapter。

```python
from coreorder.packing import LayoutBuffer, pack_batch
from _coreorder_fcn import Evaluator

buffer = LayoutBuffer(layout)  # "aos" 或 "soa"，贯穿当前 run
kernel = Evaluator(parallel=False)

# A 提供 sampled_agents、simulator.markets、已抽取的 draws 和起始调用序号。
with pack_batch(buffer, sampled_agents, simulator.markets, draws,
                first_call=first_call) as batch:
    outputs = getattr(kernel, batch.layout)(batch.inputs)
    for i, (agent_id, market_id, call_index) in enumerate(batch.metadata):
        if outputs["side"][i]:
            agent = sampled_agents[int(call_index) - first_call]
            # A 在原回填入口使用 agent、market_id、price、side、volume=1
            # 及该行 window 作为 TTL，并保留所有空 agent 列表的位置。
```

AoS 暴露只读一维结构数组，SoA 暴露包含 15 个只读一维列的 dict。metadata 为三个 int64。首行索引与调用序号独立；同一 agent 的多个市场共享 call_index，不可访问任何市场的 agent 仍占一个调用序号。所有借用数组和原生指针的有效期到 with 退出。异步消费者必须在退出前等待所有工作结束。错误批次由整次 run 记录并停止，以免已经消费的样本被重抽。

## 每批转换与字节

| 操作 | AoS | SoA |
|---|---|---|
| 对象与样本写入目标 | 每个有效 pair 做一次 15 字段结构赋值 | 同样的 15 个标量直接写入各列 |
| 身份 | 每行赋值一次，24 B | 相同 |
| 交给 B | 一次切片生成借用视图，整块复制 0 次 | 15 个借用列视图与一个新字段字典，整块复制 0 次 |
| B 串行核 | 每行用 memcpy 读一份 112 B 局部记录 | 从 15 个地址装入同型局部记录 |
| B 输出 | 分配一个输出数组，每行写入 16 B | 相同 |

上述是源码层的赋值与复制口径。标量转换、短生命周期的 Python tuple、对象访问和 B 持有 owner 均产生开销。闲置容量不搬移旧批次，增长时分配新数组并从当前状态写满有效行。`batch.stats` 返回每个输入数组的有效字节、容量字节、有效行数、容量和单列的 metadata 字节统计。24 行实例的有效输入、元数据、输出分别为 2688 B、576 B、384 B。

## 系统接入验收（INTEGRATION_PENDING）

1. A 确认批量 samples 的生产入口、market_adapter 类型与调用序号。保持原始 agent/market 顺序和 exact FCN 检查；用剩余名额 0、1、混合空结果、稀疏多市场和尾批验证分组。A 按原路径处理订单、事件与 HFT。
2. B/C 在同一个 binding 中接入 `evaluate_range(const InputView&, OutputView, begin, end)`。C 按半开区间调度并在返回前 join。A/E 用相同配置、seed、数值后端和堆模式比较 native-serial 两种布局，再比较 native-parallel workers=1/2/4。
3. E 以未修改的 py-seq/upstream 为 oracle，比对逐事件次序与 price.hex、每步账本与订单簿、最终完整 RNG（含 gauss 缓存）。首差保留 row、身份、输入 hex 与 seed；一个系统组合失败就保留该组合状态。通过全部 G2 要求后由组长签收。
4. 诊断计时从 A 首次原始采样前开始计入 draw_pack_s，直到上下文准备出 view；native_compute_s 覆盖 B 绑定往返及任务等待；rebuild_orders_s 覆盖 A 按 metadata 构造与归组，handle_orders_s 另计。正式系统时间覆盖整段模拟，完整摘要在计时外计算。统一协议冻结后由 E 执行正式实验。

## 模块验证复现

以下命令从 D 仓库根目录执行。相邻目录 `evidence-inputs/A` 和 `B` 是 STATUS 中两个固定提交的只读快照；`D-pams-research/masanorihirano-pams-6cd5381` 是固定 PAMS 源码。使用启用 VS x64 编译环境的 PowerShell。Python 依赖为 CPython 3.12、NumPy 1.26.4、SciPy 1.14.1、tqdm 4.66.6、pytest 7.4.4、pybind11 2.13.6。

```powershell
$src = (Resolve-Path src).Path
$pams = (Resolve-Path ../D-pams-research/masanorihirano-pams-6cd5381).Path
$env:PYTHONPATH = "$src;$pams"
$env:COREORDER_PAMS_FIXTURE = (Resolve-Path ../evidence-inputs/A/fixtures/pams).Path
python -m pytest -p no:cacheprovider -vv tests/layout
python tests/layout/replay_binding.py $env:COREORDER_PAMS_FIXTURE --build-msvc ../evidence-inputs/B --build-dir ../evidence-inputs/B-build
$env:PYTHONPATH += ";" + (Resolve-Path ../evidence-inputs/B-build).Path
python tests/layout/replay_live_event.py $env:COREORDER_PAMS_FIXTURE
python benchmarks/layout/pack_micro.py --fixture $env:COREORDER_PAMS_FIXTURE --output ../pack_micro_rerun.json
```

ABI 静态与动态检查、Windows 拓扑和 PMU 可观测性见 [LAYOUT_SPEC.md](LAYOUT_SPEC.md)。微基准使用真实 PAMS 末态和独立复制的测试随机状态。该耗时只覆盖 pack_batch 的进入、出视图和退出。
