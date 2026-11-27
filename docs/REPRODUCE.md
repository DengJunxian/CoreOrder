# CoreOrder 科研复现

从 `main` 检出最终科研快照，按[构建说明](../README.md#build-and-test-the-pinned-system)初始化固定子模块、安装锁定依赖并构建 Release 扩展。本机复现记录保存实际检出提交、环境和上游对象。

## 功能正确性

~~~sh
bash scripts/verify-semantics.sh results/reproduce-seed42
~~~

脚本先运行 smoke 验证，再以固定 PAMS 独立生成 seed 42 两市场参考。六个候选覆盖原版堆、增量堆、Direct AoS、Taskflow SoA 1/2/4 workers。每份 `*-comparison.json` 报告初态、事件、逐步状态、终态和完整 RNG 的比较结果。使用新的输出目录。 [华硕记录](gates/evidence/F6/demo-receipt.json)

更广的独立回归使用 `coreorder validate --suite g0` 和 `--suite g2`，为每套指定独立输出目录。华硕 C01/V01 的例数、状态和候选身份见[最终审计](gates/FINAL.md)。

## 性能与机制

[实验执行说明](EXPERIMENTS.md)给出公开候选的计划检查、本地 pilot 和配对分析命令。[实验结果](results/README.md)提供已完成 x86 数据的统计表、运行索引和图表。新主机的测量应记录本机身份并在本机完成独立验证。封存的目标机原始数据、回执和实际授权计划由团队保管。

完成后可记录自己的操作人和角色、主机与编译器、本机扩展 SHA-256、原始运行目录及命令退出状态。独立人员复现和原双人 G3 的实际状态见[最终审计](gates/FINAL.md)。
