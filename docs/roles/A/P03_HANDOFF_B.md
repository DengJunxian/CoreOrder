# P03 交接给 B

- 依赖 [C++ 公共头](../../../include/coreorder/contracts.hpp)、[NumPy ABI](../../../src/coreorder/contracts.py)、[契约](../../CONTRACT.md) 和 [FCN 样本](../../../fixtures/pams/fcn/rows.jsonl)。
- 可用接口为 `InputView`、`OutputView`、`evaluate_range(input, output, begin, end)` 声明和逐行错误码。样本价格为原 FCN 返回且尚未 tick 取整，浮点 hex，完整 RNG 以 `workload,call_index` 关联。
- 实测入口为 `.venv/bin/python -m pytest -q tests/platform/test_contract.py` 和 `.venv/bin/ctest --test-dir build -C Release -R contract_smoke --output-on-failure`。
- 待 B 交付单一 scalar/range 核、direct-serial、两布局 binding，以及 GIL、对齐、owner 与错误处理。G0 前须与 D 各自用目标编译器和 NumPy 实测 112/16 字节、8 字节对齐及全部 offset；返回实际 SHA、命令、退出码、日志与共同确认。
