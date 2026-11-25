# G1 的 E 输入

E2 MODULE_PASS，累计14 tests；三种故障均定位首差异；RNG故障在事件完全相同时仍检出。
真实上游 seq/thread/process 代表场景三层一致；进程spawn真实命令/退出码和比较在 results/acceptance/E2。
首反例包在 results/counterexamples/E2，故障明确属于测试替身，不能标记生产后端。
G1-heap：INTEGRATION_PENDING（A2 CoreOrderMarket生产实现与真实配置开关缺失）。
G1-native：INTEGRATION_PENDING（B/D 112B生产binding和A最小闭环缺失）。
接入后由组长运行统一CLI，复用 VALIDATION_SPEC.md schema，先单因素对照再组合；不得拿两套有同一错误的native实现互证。
