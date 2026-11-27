# G0 的 E 子门

E1 MODULE_PASS；整体 G0 INTEGRATION_PENDING。
6 tests真实通过，含原上游同seed重复和缺字段/状态/隐式填零拒绝；首次GBK失败及修复日志均保留。
真实上游fixture、FCN原函数输出和schema样例由 validation.fixtures生成，带来源/环境/hash。
A必须在其CLI注册 smoke/g0，输出候选同结构并与独立参考比较；B/D ABI门与公共schema冻结不由E代签。

## P04.5 组长接收

本页首段记录 E1 的独立交付。P04.5 已在本地新基线接通 `smoke` 与 `g0`，两套独立差分均通过。正式 G0 状态和复跑 SHA 以组长的当前门记录为准。 [G0 验收](G0.md)
