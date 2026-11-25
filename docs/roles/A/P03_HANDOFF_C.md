# P03 交接给 C

- 依赖 [公共头](../../../include/coreorder/contracts.hpp)、[契约](../../CONTRACT.md)、[Taskflow 锁](../../../UPSTREAM.lock.json) 和 [FCN 行](../../../fixtures/pams/fcn/rows.jsonl)。
- 可用接口为 `RowRange::valid_for(n)`、`InputView`、`OutputView` 和 B 的 range 函数声明。任务覆盖 `[0,n)` 恰好一次，每个输出槽由唯一任务写入，汇合后按原行序读取，错误传回调用方。
- 先编译 `coreorder_contract_smoke` 并运行 `.venv/bin/ctest --test-dir build -C Release -R 'contract_smoke|toolchain_smoke' --output-on-failure`。A 侧检查公共头、边界判定和工具链。
- 待 C 返回 `run_ranges` 生产签名、目标编译日志、worker 与 grain 边界、空范围和尾块、恰好一次覆盖及异常传播的实际证据。持久执行器和故障注入验收由 C 负责。
