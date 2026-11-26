# E 验证协议 v1（coreorder-r4-v1）

范围：E 的独立工具；G0/G1/G2 整体仍由真实生产模块和统一 CLI 验收。

`validation.reference.collect(config: dict, seed: int, pams_root: Path, backend="py-seq", workers=2) -> dict`
只导入逐文件验证的 PAMS `6cd53810103780770c5b5d6ee0069ccab9f4b358`，不得导入 coreorder 优化公式、堆恢复或 packing。
默认读取 A 的 `vendor/pams`；当前缺少 A 的 submodule，开发使用仓库外固定源码归档。官方 Git tree 的 blob SHA1逐个验证包内全部 Python 文件、LICENSE 和 CI2002 JSON，并拒绝额外 Python 文件。

`TraceLogger` 在日志**写入时**冻结字段，避免缓冲日志对可变对象的引用变化。原事件顺序保留，不按 ID/类型排序。
`ObservedSimulator` 仅调用原 `_update_times_on_markets` 后采集状态：覆盖所有市场 after-step hook、时间推进及过期，含初始 t=0 检查点；最终状态另采，覆盖 session-after/end。金融方法未经改写。
逐步状态包含各 agent 全部非回指字段、所有市场历史及逻辑簿、session、event/hook 注册次序、fundamentals 状态。Python Random 的完整 getstate（三段含 gauss 缓存）及 fundamentals NumPy bit_generator.state 在每检查点和最终结果保留。runner 的业务状态为其 `_prng`；线程池、logger 缓冲、时钟不入语义状态。

所有浮点使用 float.hex，数组记录 dtype/shape，字典非字符串键采用有类型的键值对编码。订单簿复制后用**原 Order 比较器**排序；expire_time_list 的原列表顺序保留（会决定到期日志次序）。事件数组绝不排序。禁止 repr/地址哈希；未知状态类型直接报错，扩展模型必须先审查序列化支持。

`validation.compare.compare(reference: dict, candidate: dict) -> dict` 先核身份，再按 events/steps/final/rng 顺序做结构比较。SHA256仅作索引，传入 hash 相同也必须比较结构。结果非 PASS 不计成功。
`save_reproducer(reference, candidate, directory, ...) -> report` 保存原配置、seed、首差异路径及邻接事件/状态、完整结构和 RNG；包中的 replay 命令重新执行比较。它是首反例包，未宣称已做配置 delta debugging。

现金守恒只在无费模型用绝对 1e-7 加相对 1e-12 的容差（见 E2 实现），证券数量严格相等。路径比较始终 exact，不以此容差放宽价格或账本差分；不要求单账户余额非负。

## A 的接入点

A 在自己的 `coreorder validate --suite smoke|g0` 中调用 collect 和 compare，并为候选采用同一 Logger 与 Simulator 观察点。E 不创建 A 的 CLI 或生产 runner。
最小示例：

```python
from validation.reference import collect
from validation.compare import compare
reference = collect(config, seed, "vendor/pams")
# A 用真实生产 runner + TraceLogger/ObservedSimulator 输出相同 schema
report = compare(reference, candidate)
assert report["status"] == "PASS"
```

standalone 命令：`python -m validation collect --config CONFIG --pams-root vendor/pams --seed 42 --output trace.json.gz`。
`python -m validation compare --reference oracle.json.gz --candidate actual.json.gz --bundle results/counterexamples/unique-id`。

## schema 评审交 A

`validation/manifest.schema.json` 为公共包 schema 原样副本，不修改 A 的 schemas。`validate_record` 补充跨字段检查：运行状态、SHA、time 缺测理由、采集来源、超时右删失、区组身份、run_id 一致。零可为真测量，但没有 measured/derived 来源的填零被拒绝。NOT_RUN/FAIL/TIMEOUT/UNSUPPORTED、dirty、warmup、requested/effective 不同都不能进入正式摘要。
建议 A 冻结时间指标来源和 missing_reasons、validation_run_id 的共享 schema；E 的实现不等于 A/E 已共同签署公共 schema 或 G3 协议。

## fixture 与证据范围

E1 生成上游短 CI2002（8 agents、两 session 各3步、M3）、数值输入/原函数输出、schema 样例。原 CI2002 文件保持未修改，缩短版另存且单独 hash。
E2/E3 覆盖表与真实状态由 `results/acceptance` 和 `docs/gates` 引用。公共包的 parity/heap/native probe 是历史先验，不计本轮通过。M1、空单/补批、partial、ties、cancel、expire、market/limit、fixed/normal、多市场、HFT 必须逐类列出；缺生产模块的对照只记 INTEGRATION_PENDING。
