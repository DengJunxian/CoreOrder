# P03 公共真实 fixtures

以下资料来自固定 PAMS 的真实运行。统一 seed 为 42，PAMS 完整 SHA、生成命令、解释器及依赖版本、生成脚本和每文件 SHA-256 见 [manifest](pams/manifest.json)。使用冻结的 P01/P03 环境执行 [generate.py](generate.py)。

| 目录 | 输入和实际观察 | 用法 |
| --- | --- | --- |
| [ci2002-smoke](pams/ci2002-smoke/config.json) | P02 的 CI2002 派生配置，24 个普通代理、M=1、80 步，80 笔订单和 14 笔成交 | 完整交易事件、80 步市场与全局状态、最终账户和簿、市场历史及最终 RNG |
| [event-state](pams/event-state/config.json) | 12 个代理、24 步、短 TTL 与原版 `FundamentalPriceShock`。step 10 的基本面由 300 变为 270，原订单簿产生 20 笔过期 | 用于确认真实事件的效果、TTL 和逐步状态 |
| [fcn](pams/fcn/rows.jsonl) | 直接观察原版 `FCNAgent.submit_orders_by_market` 及同一次调用的 `Random.gauss` 返回，fixed、normal 各 12 行，包含买卖两方向 | 浮点字段为 hex，按 dtype 字段名转换到原生 AoS 或相同 SoA 列。订单价格为入簿 tick 取整之前的 FCN 返回值。完整逐调用 RNG 位于同目录 `rng.json.gz`，以 `workload,call_index` 对应 |

使用 `gzip -dc` 或 Python `gzip.open` 读取压缩 JSON/JSONL。现有 fixture 路径受保护。可在同环境生成到新目录并比较两个 manifest 的 `files` 映射。

```sh
.venv/bin/python fixtures/generate.py --output results/rebuilt-p03-fixtures
.venv/bin/python -m pytest -q tests/platform/test_contract.py
```

FCN 样本覆盖同环境真实的基础数值路径。无单、反向 chart sign、跨机器逐位相等和生产 binding 的验证留待相应阶段。A 的交易与状态观察记录供 E 对接，E 的独立 collector 和首差异判定由 E 交付。
