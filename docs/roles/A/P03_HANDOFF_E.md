# P03 交接给 E

- 依赖 [契约](../../CONTRACT.md)、[记录 schema](../../../schemas/records.schema.json)、[fixtures 与来源](../../../fixtures/README.md) 和 [固定 PAMS](../../../UPSTREAM.lock.json)。A 的 `coreorder.reference` 直调原版 PAMS，使用 A 的观察器，适合核对输入输出格式。
- 独立 collector 应直接调用固定未修改 `SequentialRunner`，用 E 自己的采集和比较逻辑核对 `py-seq/upstream`。对比逐条产生的事件、首个 `MarketStepEndLog` 处的逐步全局状态与最终完整 RNG，并输出最早差异、输入和 seed。RNG 包括 gauss 缓存和 fundamentals 的 NumPy 状态。
- 在 `validation/e1.py` 实现 `python -m validation.e1 --suite smoke|g0 --config <absolute-json> --seed 42 --output <new-directory>`。CoreOrder CLI 以仓库为 cwd，传入 smoke 配置和全新 `<output>/e1` 目录，保留退出码与 stdout/stderr。smoke 覆盖最小真实交易，g0 按验收规范增加既定真实 fixture 和门禁检查。
- 子入口仅在必需检查实际完成且通过时返回 0。新生成的 `status.json` 应包含 `suite`、`git_sha`、`contract_version`、`status` 以及 `checks` 映射，`events`、`step_state`、`final_rng` 各填真实状态字符串。CLI 同时检查退出码、身份及所需状态。当前入口缺失时两套 suite 均 BLOCKED，退出 3。
- A 侧复测为 `.venv/bin/python -m pytest -q tests/platform/test_contract.py tests/platform/test_py_seq.py`。E 返回独立入口实现、首差异证据、两套真实命令和结果。G0 仍须收到 B/C/D 确认并通过组长复审。
