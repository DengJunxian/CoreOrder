> GitHub轻量交付分支 `e/03-github-delivery`：源码和测试与原交付一致；下文完整原始轨迹、profile和反例包位于单独交付的 `CoreOrder_E1-E3.bundle`，不重复放入代码PR。当前分支保留日志、结果元数据和代表fixture。归档SHA256、源文件校验值及恢复命令见 `docs/roles/E/EVIDENCE_ARCHIVE.json`。

# E1–E3 交付与接入

GitHub提交入口为 `e/03-github-delivery`，源码提交533ab8747432a3d0e06c7c0fb248eb049dd0d880，经26个源文件逐一SHA256核对及31 tests/pip check干净复测。最终推送HEAD可由git rev-parse HEAD取得；它是原完整交付的轻量发布快照，原阶段历史和完整raw通过单独bundle归档。

E 的独立工具已实现；G0/G1/G2 系统验收均 **INTEGRATION_PENDING**。不把 vendor 自身对照、测试故障或历史 probe 当生产模块通过。
最终验证源码：`52260be7cca066b896de7c7f266552add93a82cb`。干净工作树完整复核在 `results/acceptance/E3/clean-52260be`；后续证据提交仅追加文档/raw。阶段commit链见 `COMMITS.json`。

## 代码入口

| 模块 | 实际签名/职责 |
|---|---|
| 上游核验 | `validation.upstream.load(root: Path) -> pams_module`，逐 blob 校验后拒绝跨安装目录导入 |
| 独立参考 | `validation.reference.collect(config, seed, pams_root, backend="py-seq", workers=2) -> dict` |
| 观察器 | `TraceLogger()`、`ObservedSimulator._update_times_on_markets(markets)`，只观察原转移 |
| 精确比较 | `compare(reference: dict, candidate: dict) -> dict`，身份/事件/step/final/RNG |
| 不变量 | `check(trace: dict, abs_tol=1e-7, rel_tol=1e-12) -> dict`，仅无费模型 |
| 首反例 | `save_reproducer(reference, candidate, directory, reference_path=None, candidate_path=None) -> report` |
| 候选门 | `evaluate_cell(reference, candidate, manifest, status, expected: dict) -> dict` |
| 结果契约 | `validate_record(manifest, metrics, status) -> True`；`eligible(...) -> bool` |
| 命令记录 | `experiments.capture.execute(command: list[str], directory, timeout=30) -> dict` |

CLI 为 `python -m validation collect|compare|replay`；真实 fixture 生成 `python -m validation.fixtures`；独立回归 `python -m validation.matrix`。E 不修改 `coreorder` 统一 CLI。

## 复现（仓库根目录）

用 CPython3.12 创建独立 venv，按 `docs/roles/E/requirements.lock.txt` 安装；执行 `python -m pip check`。A 未交 vendor 时用官方 codeload 固定归档（非生产依赖引入）作为外部研究源码：
`https://codeload.github.com/masanorihirano/pams/zip/6cd53810103780770c5b5d6ee0069ccab9f4b358`。
解压后把 `COREORDER_PAMS_ROOT` 指向其根目录。核验器逐个检查 `validation/upstream-files.json` 的官方 Git blob，修改过的源码不能充当 oracle。

```powershell
$env:COREORDER_PAMS_ROOT = (Resolve-Path 'PATH_TO_FIXED_PAMS').Path
New-Item -ItemType Directory -Force .cache | Out-Null
python -m pytest tests/differential -q --basetemp .cache/unique-test-id
python -m validation collect --config results/fixtures/E1/config.json --pams-root $env:COREORDER_PAMS_ROOT --output results/unique-trace.json.gz
python -m tests.differential.fault_demo --pams-root $env:COREORDER_PAMS_ROOT --output results/generated-counterexamples/unique-id
python -m validation replay --bundle results/generated-counterexamples/unique-id/missing-gauss
```

最后一条命令**应返回1并报告差异**：它重放故意漏采 gauss 的测试故障；不能作为正常生产运行失败。每次输出路径必须唯一；工具拒绝覆盖 raw。pytest 的 basetemp 同样使用新目录，避免碰已有文件。

## A 的生产接入示例（尚未执行）

以下片段在 A 交付真实 runner 后执行。`runner` 是 A 在当前模式/布局/恢复配置下创建的真实生产实例，构造时传入 `TraceLogger` 和兼容的 `ObservedSimulator`；不在此提供替代 runner。

```python
from validation.codec import snapshot, digest
from validation.compare import compare
from validation.reference import collect
reference = collect(config, seed, "vendor/pams")
logger.runner_rng = runner._prng
runner._setup()
initial = snapshot(runner.simulator, runner._prng)
runner._run()
logger._process()
final = snapshot(runner.simulator, runner._prng)
candidate = dict(contract_version=reference["contract_version"],
    upstream_sha=reference["upstream_sha"], config=config,
    input_hash=digest(config), seed=seed, initial=initial,
    events=logger.events, steps=logger.steps, final=final, rng=final["rng"])
report = compare(reference, candidate)
```

A 应映射经批准的 CoreOrderMarket 非业务诊断字段至同一市场角色；不能宽泛忽略未知状态来凑一致。若候选 simulator 无法直接继承此观察器，A需提供相同“全部市场 after-step hooks + 时间推进后”的只读回调；MarketStepEndLog本身早于after-step hook，不足以替代。effective PAMS JSON、原始JSON hash与实际后端元数据须由A的manifest保存。

## 待集成依赖与验收

| 所有人 | 缺失输入 | 验收方法 |
|---|---|---|
| A | G0固定vendor/submodule、共享schema、CLI smoke/g0/g1/g2、生产runner和heap切换 | 注册E工具；同配置逐事件/逐step/最终RNG对独立reference；只改恢复段人工审阅；8类定向簿操作后继续新订单 |
| B | 112B AoS/16B结果binding与同一scalar公式、GIL/buffer错误报告 | 原FCN输出和每次Random状态差分；1万有效样本；错dtype/stride/offset1/非finite必须拒绝；ASan/UBSan由B提供 |
| C | 持久Taskflow执行器/静态分块 | 真正serial不建executor；parallel1/2/4且ranges恰好覆盖；扰动任务完成顺序后事件/RNG不变；异常不半提交 |
| D | 同字段AoS/SoA与live packing、容量/重分配记录 | 同backend同恢复同seed两layout；0/1/grain±1/尾块/不可访问市场；无共享公式替代oracle |
| A/B | 未支持agent、IndexMarket等error/显式整run fallback | 真生产CLI错误退出；fresh seed整run后备，manifest effective=py-seq；原生汇总排除后备 |
| 组长 | 真实候选SHA及统一集成基线 | 本文件的7设置×12fixture×5seed主矩阵，加08要求的有限组合/边界补充；G2缺核心不得签PASS |

公共ABI的上游接口仍以R4为准：B `evaluate_range(input_view,output_view,begin,end)`，C `run_ranges`，D input_view/pack；E不实现这些核心函数。没有生产实现时不生成伪造manifest或吞错返回PASS。
动态调度若启用另验；真实HFT支持仅覆盖内置MarketMakerAgent。费用模型明确未纳入本模块守恒支持。跨ISA/libm、原生sanitizer、真实PMU均未运行。正式pilot/G3/性能统计属于E4，当前停止。

## 证据目录

- `results/fixtures/E1`：真实上游轨迹、FCN输入/原函数输出、schema样例与来源hash。
- `results/acceptance/E1|E2|E3`：完整命令、exit code、stdout/stderr、环境、失败及修复；E3/matrix-repair1含120个压缩完整trace和60个比较记录。
- `results/counterexamples/E2`：三个测试故障的原始配置、首分歧与压缩结构。
- `results/diagnostics/E3`：profile/低开销诊断与验证器微基准，全部标明开发用途，不能进正式系统性能图。
- `results/acceptance/E3/clean-52260be`：最终dirty=false证据，120条完整R4 validation记录、31 tests、真实normal进程代表场景与依赖检查。
- `docs/gates`：门状态；`RESEARCH.md`与`PAPER_NOTES.md`：来源、决策、研究边界。

本轮远端连接器账户只有pull权限，push=false；无远程写入/PR/合并动作。提交链与bundle在最终回执给出，组长可在自己的授权下获取；不能把本地分支描述为已上传GitHub。
