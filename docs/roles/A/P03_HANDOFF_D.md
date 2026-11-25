# P03 交接给 D

- 依赖 [C++ 公共头](../../../include/coreorder/contracts.hpp)、[NumPy dtype](../../../src/coreorder/contracts.py)、[状态记录 schema](../../../schemas/records.schema.json) 和 [FCN 样本](../../../fixtures/pams/fcn/rows.jsonl)。
- `AosInputView` 和 `SoaInputView` 借用同顺序的 15 字段，metadata 在布局之外，输出槽保留原行序。按 `float.fromhex` 还原输入，整数列使用 dtype 对应宽度和本机字节序。
- 运行 `.venv/bin/python -m pytest -q tests/platform/test_contract.py` 并在自身目标编译器运行 `contract_smoke`。检查每列 stride、实际地址和 owner 生命周期。
- 待 D 交付两布局、packing 与容量记录，复用容量时每批刷新参数。与 B 核对 sizeof、alignof、offsetof、dtype 和目标平台实际字节，将命令和退出码连同确认交回 A。
