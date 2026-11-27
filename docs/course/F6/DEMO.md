# F6 实跑 Demo

**PASS，华硕 x86，seed 42。** 原生产 checkout 检出 `58ec5764c21833142c50abacd9e2302404ffdb06`，实载原生扩展与 F2/F3 相同。原版独立 PAMS 参考有 **184 个有序事件、89 个订单、28 笔成交、25 个到期**。stock 堆、增量堆、原生 direct AoS 与 Taskflow SoA 1/2/4 workers 六种候选均通过初态、事件、逐步状态、终态和完整 RNG 的差分。整段功能命令退出 0。 [目标机回执](../../gates/evidence/F6/demo-receipt.json)

## 现场

从已经按锁构建的生产根目录使用一个新的输出路径。项目入口沿用已测脚本。

```bash
git rev-parse HEAD
git submodule status --recursive
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
bash docs/gates/evidence/P15/demo.sh results/course-live-seed42
```

讲到团队第 17 页，在 `events.jsonl` 展示四 worker 的第一份订单和第一笔成交，再读六份差分 JSON。回执中 oracle 的全事件序号 10 是市场 1、代理 9 的限价卖单。序号 17 是市场 0、买方 5 与卖方 12 的成交。价格保留十六进制原值。各候选终态摘要一致，完整 RNG 摘要一致。现场用时属于功能流程，历史性能引用低开销配对实验。

```bash
out=results/course-live-seed42
rg -m 1 '"event_kind":\s*"order"' "$out/parallel-soa-w4/events.jsonl"
rg -m 1 '"event_kind":\s*"execution"' "$out/parallel-soa-w4/events.jsonl"
cat "$out/"*-comparison.json
```

## 离线

受限归档的 `offline/` 保留此轮参考和四 worker 候选。Mac 用 `sandbox-exec` 禁止网络后实际复查，五个差分范围全部通过。无运行环境时，可播放已嵌入中文字体的 [团队 PDF 第 17 页](CoreOrder-Defense.pdf#page=17)，在 [可读回执](../../gates/evidence/F6/demo-receipt.json) 中打开真实事件和运行摘要。

```bash
.venv/bin/python -m validation compare \
  --reference "$COREORDER_F6_ARCHIVE/offline/reference.json.gz" \
  --candidate "$COREORDER_F6_ARCHIVE/offline/candidate.json.gz"
```
