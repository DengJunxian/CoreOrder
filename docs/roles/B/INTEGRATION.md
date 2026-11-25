# B 模块接入与验收

开发候选 `f867a4fb07c928f459fa8b6d3e84a95ee88b1742`，契约 `coreorder-r4-v1`。生产范围为 `native/fcn/` 和 `native/bindings/`。依赖 A 的 [公共 C++ 头](../../../include/coreorder/contracts.hpp)、[NumPy ABI](../../../src/coreorder/contracts.py) 和锁定的 pybind11 2.13.6。C++ 内核独立依赖 C++17 与 libm。PAMS 执行行情、随机数和订单逻辑，固定版本见 [锁文件](../../../UPSTREAM.lock.json)。生产并行适配进入同一个绑定时另需 C 的 Taskflow 运行时。

## A 与 D 接入

用 C++17 编译 `native/fcn/evaluate.cpp` 和 `native/bindings/fcn_binding.cpp`，包含公共 `include/`，链接 pybind11 模块目标。GCC/Clang 的正式构建使用 `-O3 -fno-fast-math -ffp-contract=off`。只接串行时使用 `native/bindings/module.cpp` 的 `_coreorder_fcn` 注册入口。加入 C 后，在同一个模块初始化点调用 `coreorder::binding::bind_fcn(module, factory)`。编译参考 [独立 CMake](../../../tests/native/CMakeLists.txt)。

```python
from _coreorder_fcn import Evaluator
from coreorder.contracts import INPUT_DTYPE, OUTPUT_DTYPE

evaluator = Evaluator()  # 每次 run 持有一个对象
assert packed_aos.dtype == INPUT_DTYPE
output = evaluator.aos(packed_aos)
assert output.dtype == OUTPUT_DTYPE
# 两种布局选择其一。packed_soa 是 D 的 15 个同长连续 NumPy 列。
output_from_soa = evaluator.soa(packed_soa)
```

- A 按原访问规则和市场顺序准备输入。D 提供原生端序的 `INPUT_DTYPE` 一维记录，或 15 个按字段名索引的标量列。每列必须满足自身的 stride 和对齐。长度为 1 的 AoS 字段切片可能被 NumPy 标为连续，却仍有 112 字节 stride，D 要提供实际紧密排列的列。
- 每行输出为原始 price、side、error。一行失败时整批抛 `ValueError`，内容含最早的行索引及 R4 错误码。A 以行索引关联 metadata，记录首差的 agent、market、call index、原始数值 hex 和相关 RNG。失败批次停止，保持实际后端记录。成功时以 `side != 0` 判定回填订单，继续使用上游 `Order`、tick 处理和提交顺序。
- 入参数组和可写别名从调用开始至返回由调用方保持不变，包括其他线程以及复用的 D 缓冲。返回数组为绑定独立分配。生产绑定没有自动复制、cast 或重排输入。AoS 内核按单行读入局部 C++ 记录，避免把 NumPy 存储当作已构造的 C++ 对象。

## C 接入

无 Python 的数值签名在公共头内。C 在每个分配到的半开区间调用同一函数。`output.size` 应等于输入总行数，每个任务只写 `[begin,end)`，空区间可用。行错误保存在调用者给的输出槽。视图或范围本身非法时抛 C++ 异常。

```cpp
void coreorder::evaluate_range(const InputView& input, OutputView output,
                               std::size_t begin, std::size_t end);

// native/bindings/fcn_binding.hpp
using RangeTask = std::function<void(std::size_t begin, std::size_t end)>;
using RangeExecutor = std::function<void(std::size_t rows, std::size_t grain,
                                         Schedule schedule, const RangeTask& task)>;
using ExecutorFactory = std::function<RangeExecutor(std::size_t workers)>;
```

接入示例为 `bind_fcn(module, make_executor)`。`make_executor(workers)` 由 A/C 按 C 正式 `run_ranges` 签名实现。它返回持有一个持久 C 运行时的函数，调用时传递 `rows`、`grain`、调度策略及 `task`。C 运行时需在正常返回和传递异常之前都结束全部任务。收到 C 的真实签名后，将 `Schedule::{static_partition,dynamic_partition}` 映射到其原生选项。此层不创建 Python 回调。接好后 Python 用 `Evaluator(parallel=True, workers=4, grain=128, schedule="static")`，仍调用同样的 `aos` 和 `soa`。

## GIL 审计

| 时点 | 行为 |
| --- | --- |
| GIL 持有 | 校验 NumPy 确切 dtype、shape、stride、原生端序、ALIGNED 与地址余数。保存各输入数组的独立 owner 并分配、检查返回数组。 |
| GIL 释放 | 按一个直接串行 range 或 C 的运行时遍历原生指针。工作函数持有原生 view，使用调用者分配的独占写槽。并行实例通过非阻塞锁拒绝重入。 |
| 恢复 GIL | 同步执行已结束。依行号扫 error，成功返回数组，或抛出 Python 异常。随后释放 Python owners。异常展开也先恢复 GIL。 |

## 联调验收

| 状态 | 责任与验收 |
| --- | --- |
| `MODULE_PASS` | B 已用候选头、两种输入布局、公开 fixture 与同机真实 PAMS 检查每行订单和完整随机状态。`std::async` 用于测试工厂调用、区间和并发输出，作为 B 的独立替身。 |
| `INTEGRATION_PENDING` | D 交付真实 packing 后，对 0、1、尾块长度和复用缓冲检查两种布局，以及所有输入列 stride、实际地址与 metadata 行序。D 回交目标编译器的 ABI 独立复核。 |
| `INTEGRATION_PENDING` | C 提供生产工厂，C/B 验证持久 executor、空调用、尾块、1/2/4 workers、两种调度、异常 join 和输出逐字节一致。生产模块未接入时，`parallel=True` 明确报错。 |
| `INTEGRATION_PENDING` | A 接入 runner，E 用原版 PAMS 和独立比较器，在固定配置、种子和 `book_restore=upstream` 下比较 `py-seq` 对 `native-serial` 与 `native-parallel`。至少覆盖 CI2002 smoke、事件场景、两布局、1/2/4 workers，逐事件、逐步状态、最终 RNG 与首差上下文全部复核。 |
| `NOT_RUN` | 正式全系统性能实验须待组长冻结协议，模块微基准只提供接口成本的本地诊断。 |
