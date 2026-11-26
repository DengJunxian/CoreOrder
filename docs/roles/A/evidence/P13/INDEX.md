# P13 raw 索引与复算

## 正式 H01/E05

G3 为 `BLOCKED`。正式 H01 和 E05 均为 `NOT_RUN`，接收的正式 raw 为 0。候选清单的 `run_id` 全为空，可据 `id`、`block_id`、配置和 seed 查询待采集的条件。 [条件状态表](formal-status.json) · [G3 判定](../../../../gates/G3.md) · [计时清单](../../../../../configs/experiments/runlist-timing.jsonl) · [E05 清单](../../../../../configs/experiments/runlist-E05.jsonl)

P12 的三个原始目录均是 seed 11 诊断。每份目录保存 manifest、metrics、status、environment 与压缩轨迹，另有原版 oracle。三个 E gate 均拒绝 `input_hash`，E records 均拒绝 `setup_s` 的量测来源，`formal_eligible=false`。 P12 实际 raw (`$COREORDER_ARCHIVES/CoreOrder-P12/results/acceptance/g3/p12/chain/raw`) · [逐文件校验与 E 拒绝记录](../../../../gates/evidence/P12/lineage.json) · [P13 复核日志](audit.txt)

## P11 诊断归档

P11 raw 位于 CoreOrder-P11 诊断目录 (`$COREORDER_ARCHIVES/CoreOrder-P11/results/pilot/p11`)。主台账逐条给出原始目录、方式、命令耗时、退出状态和摘要。两次 W2-H 原版计数尝试达到 30 秒诊断限额，受限记录和使用 60 秒上限的同条件复跑均保留。 完整运行台账 (`$COREORDER_ARCHIVES/CoreOrder-P11/results/pilot/p11/runs/chronological-final.json`) · 补充运行 (`$COREORDER_ARCHIVES/CoreOrder-P11/results/pilot/p11/supplement`)

| 证据 | 原始文件入口 | 生成的可核查数据 |
| --- | --- | --- |
| 有序金融行为与工作量 | `runs/<workload>-<seed>-py-seq-<restore>-verify/` 的 `events.jsonl`、`summary.json`、`manifest.json`、`effective_config.json`，三工作负载、seed 11/29、两恢复方式 | 六对有序文件哈希及事件数见[复核日志](audit.txt)。 W1-H seed 11 原版实例 (`$COREORDER_ARCHIVES/CoreOrder-P11/results/pilot/p11/runs/W1-H-11-py-seq-upstream-verify`) |
| 簿深、暂取量、比例和比较次数 | 局部计数运行目录中的 `heap.json`。重试路径以主台账的 `run` 字段为准 | 全部 30,380 条观测 (`$COREORDER_ARCHIVES/CoreOrder-P11/results/pilot/p11/tables/heap-events.csv`) · [双侧原始分位表](../P11-heap.csv) · [逐侧制图表](figures/heap-mechanism-pilot.csv) |
| 低开销端到端观察 | `runs/*-timing/`，使用原 Logger，终态摘要在计时外 | [逐次用时与摘要](../P11-runs.csv) |
| W1-H seed 11 的剖析与单独阶段计时 | `runs/*-profile/profile.prof` 和 `runs/*-phases/phases.json`。E 的原版紧凑日志对照见 `supplement/E-W0-CI2002-*`、`supplement/E-W1-H-*` | cProfile 导出 (`$COREORDER_ARCHIVES/CoreOrder-P11/results/pilot/p11/tables/cprofile.csv`) · [阶段计时导出](../P11-phases.csv) |
| W2-H seed 11 的真实生产输入 replay | `runs/W2-H-11-native-serial-incremental-capture/` 实际采集 8,192 行，`supplement/replay.json` 记录 2,048 次核调用及输出字节校验 | 采集目录 (`$COREORDER_ARCHIVES/CoreOrder-P11/results/pilot/p11/runs/W2-H-11-native-serial-incremental-capture`) · replay 原记录 (`$COREORDER_ARCHIVES/CoreOrder-P11/results/pilot/p11/supplement/replay.json`) |
| 实际编译与主机限制 | `build.log`、`host.log`、`identity.log`、`environment.json` | 主机原始记录 (`$COREORDER_ARCHIVES/CoreOrder-P11/results/pilot/p11/host.log`) · 运行环境 (`$COREORDER_ARCHIVES/CoreOrder-P11/results/pilot/p11/environment.json`) |

## 从 raw 再生成机制图

只有 GitHub checkout 时，可用已随仓库提供的分位表重新制图。在安装 Matplotlib 3.11.2 的 Python 环境下，从仓库根目录运行 `python docs/roles/A/evidence/P13/figures/gen_fig_heap_mechanism.py`。下列完整原始链路需要另存的本机归档。

在 P11 和 P13 两棵相邻工作树均可读的情况下，以下命令复用 P11 汇总脚本。它从 `chronological-final.json` 找出真实的 `heap.json`，逐条检查 `n=h+k` 和恢复比例，比较两路径有序的双侧堆观测与实际调用次数，再导出汇总。P13 用 Matplotlib 3.11.2 生成 300 DPI PNG 和嵌入字体的矢量 PDF。使用新导出的 raw 汇总和仓库内可移植的 P11 CSV，各自生成的三份制图产物逐字节相同。

```sh
cd $COREORDER_ARCHIVES/CoreOrder-P11
p13_tables="$(mktemp -d /tmp/coreorder-p13.XXXXXX)/tables"
PYTHONPATH="$PWD" .venv/bin/python -B results/pilot/p11/summarize_p11.py \
  "$PWD/results/pilot/p11/runs" "$p13_tables"
cd ../CoreOrder-P13
$LOCAL_HOME/.codex/venvs/research-skills/bin/python -B \
  docs/roles/A/evidence/P13/figures/gen_fig_heap_mechanism.py \
  "$p13_tables/heap-summary.csv"
```

跨机器复算可先核对原始 CSV 和绘图源的散列。 [核对日志与 SHA-256](audit.txt) · [脚本](figures/gen_fig_heap_mechanism.py) · [机制图 PNG](figures/heap-mechanism-pilot.png) · [机制图 PDF](figures/heap-mechanism-pilot.pdf)
