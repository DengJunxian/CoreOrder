# CoreOrder R4 实验执行与分析

从仓库根目录运行。先按 README 安装锁定环境和 Release 扩展。使用构建目录提供已核验的原生模块。R4B 修订后的候选位于 `configs/experiments/r4b`，旧目录保留 P12 历史和开发 pilot 的参数。

```sh
export PYTHONPATH="$PWD/build"
.venv/bin/python -m experiments.run --plan configs/experiments/r4b --stage check
.venv/bin/python -m experiments.run --plan configs/experiments/r4b --stage C01 --case C01-C01f-M0-101-5 \
  --output results/c01-m0
.venv/bin/python -m experiments.run --stage pilot --budget-seconds 90 \
  --output results/r4-pilot
.venv/bin/python -m analysis.report --input results/r4-pilot --output results/r4-pilot-report \
  --development
```

`check` 校验候选文件和工作负载的 SHA-256、C01 与 V01 的参考关系、warmup、待测条件、区组随机顺序及冻结统计规则。C01 和 V01 可以在 G3 生效前运行。`--case` 可重复指定，执行器自动纳入相应参考运行。pilot 复用冻结 E02 的 native-direct 和 native-2 条件，在 C01b 的六步工作负载上使用 pilot seed 11、29，各做两个技术重复。还会采集一次独立参考、每个条件的差分、每个变体的预热和两条剖析。

安装图表依赖到独立目录，保持实验运行环境及其依赖身份。绘图读同一套封存 raw，PDF、PNG 和来源索引由同一报告生成。

```sh
.venv/bin/python -m pip install --only-binary=:all: --target results/plot-deps \
  -c requirements.lock -r analysis/requirements.txt
PYTHONPATH="$PWD/results/plot-deps" .venv/bin/python -m analysis.report \
  --input results/r4-pilot --output results/r4-pilot-figures --development --figures
```

## 回执与断点

每阶段创建新的输出目录。目录级 `batch.json` 固定源码、目标环境、扩展 SHA-256、计划摘要、执行批次及预算。每条尝试位于 `raw/<case_id>/<run_id>/`，含子进程实际命令、退出码、原始日志、产物和完整性索引。每次成功的候选验证生成 `validation-receipt.json`，绑定实际候选 run ID、独立原版 run ID、原始及规范化配置、有效配置、seed、后端、运行时、差分和守恒回执的 SHA-256。正式和 pilot 的 timed run 都核验这份回执以及同次运行的终态和完整 RNG。

`--resume` 要求相同输出目录、阶段、筛选、预算、源码、二进制和环境。已封存的结果包括超时及失败，按冻结顺序从下一个待执行位置继续。中断时保留原目录与已写文件。如果此前的进程树清理待确认，可在确认所有旧工作进程退出后，对同一个目录使用 `--resume --acknowledge-interrupted`，系统会记录确认。超时保留真正的子进程退出码及右删失记录。`--budget-seconds` 可收紧会话总预算。计时尝试使用同用户主机锁串行执行，封存和清理的实际时间计入预算。超时后完成进程树清理再检查余量。重测使用独立批次和原始目录，已批准的同一正式阶段只允许续跑原批次。

## 正式准入

当前冻结候选的 G3 状态为 `BLOCKED`。正式 `timing` 和 `E05` 要求 A/E 在目标 x86 上共同批准生效的计划目录，并传入该版本真实生成的 V01 原始批次。应把激活目录放在受测源码工作树之外，保留验证与计时阶段相同的源码 SHA、锁定依赖、有效配置、环境和二进制。

激活计划的两份文件须一致标示 G3 `PASS` 并开放执行。锁绑定目标 x86 环境、实际严格编译参数、CPU 亲和性和频率记录，以及每条 V01 的 `{run_id, sha256}`。A、E 的批准文件包含 `role`、`reviewer`、`status` 和 `protocol_lock_hash`，并在锁中登记文件相对路径和 SHA-256。锁 ID 使用 [协议校验器](../experiments/protocol.py) 中的规范化摘要，排除相互包含的签认与锁文件字段。执行器逐项核对 V01 原始轨迹、差分、守恒和批次身份。正式 stage 使用 `--plan <approved-dir> --receipts <sealed-V01-dir>`，分析使用相同两项参数。正式主机将 OpenMP、OpenBLAS 和 MKL 外部线程数固定为 1。

E05 的 PMU 子表需要批准的实际事件组。replay 需要目标机上按原顺序捕获的真实 FCN 行、其来源 V01、输入及二进制指纹和复算次数。replay 图度量生产绑定、缓冲分配及任务等待，记录独立的计量区间。profile 标明包含式范围，恢复时间可包含在订单处理时间内。

## 统计和图表

分析按照同一主机、工作负载、seed、repeat、配对组和 block 配对。先计算每个区组的 `log(T_reference / T_variant)`，再对同 seed 的三个技术重复取中位数，最后对五个 seed 的效应等权求均值并取指数。Bootstrap 用冻结 seed 73021 对五个 seed 进行 10,000 次重采样，输出 95% 区间。并行效率为匹配的原生串行基线 speedup 除以相对 worker 数。报告同时保留原始毫秒、median、IQR、逐 seed 效应、失败、超时、预热和缺测。任一要求区组缺失时，对应主估计和区间为空。

`report.json` 保存估计、全部配对状态及原始回执定位，`runs.csv` 保存逐次运行数据。可用 `--diagnostics` 与 `--correctness` 加入同身份原始批次。图表覆盖正确性、堆恢复、原生化、worker 扩展、效率、布局、准备与计算阶段、工作集 replay、PMU 和瓶颈迁移。没有合格数据的图表在 `figures/lineage.json` 中标为 `NOT_RUN`。单机 pilot 图注明开发范围，正式区间沿用完整的五 seed 规则。

本机复现的真实命令、退出码、回执 SHA-256 和图表来源见 [R2B 验收记录](gates/evidence/R2B/README.md)。
