# 成员 A 研究记录

## P01 固定研究底座

PAMS 的 PEP 517 元数据由固定提交声明的 `uv_build` 生成。按锁构建 wheel 并记录来源，在不修改上游源码的前提下给后续独立差分保留稳定的参考入口。后续应从固定 `SequentialRunner` 和官方 CI2002 验证平台行为。

测试扩展验证了 ARM64 上 C++17、pybind11 与 Taskflow 可联用。Release 编译命令含 `-O3 -fno-fast-math -ffp-contract=off`。该记录的证据范围为构建、扩展加载与两个独立任务的结果，另见 [P01 日志](evidence/P01.txt)。
