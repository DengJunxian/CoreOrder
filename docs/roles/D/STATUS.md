# 成员 D 交付回执 · D1 至 D3

交付分支 `d/01-03-layout`。契约 `coreorder-r4-v1`。三个阶段的独立技术任务完成，模块验收为 **MODULE_PASS**。下表的远端提交保留了三个开发阶段，均可独立审查。仓库主线基线为 [e2492a4](https://github.com/DengJunxian/CoreOrder/commit/e2492a4b8317c6674918b13470b577f4d6f8675d)。A 和 B 的候选模块仅在仓外用于对照验证。

| 阶段 | 已完成及证据 | GitHub 实现提交 |
|---|---|---|
| D1 | 固定源码热字段审计、C++/NumPy 对齐与 21 个字段往返、Windows 硬件清单。[ABI 锁定环境复验](evidence/abi_r4runtime.txt) · [布局说明](LAYOUT_SPEC.md) | [440940d](https://github.com/DengJunxian/CoreOrder/commit/440940d200689172c25073bb6036b74be08b4e3b) |
| D2 | 可复用的 AoS、SoA、只读租用与缓冲校验。真实 B 串行核对 24 行公共 fixture，两布局输出与记录逐字节一致。[单测](evidence/buffers-unittest.txt) · [B 的现场编译与回放](evidence/binding-replay.txt) | [a56e485](https://github.com/DengJunxian/CoreOrder/commit/a56e485c11203827458d425b5e64ac77486ba24b) |
| D3 | 实时字段和 metadata 打包、稀疏多市场、变参刷新、错误恢复与独立微基准。真实基本面冲击前 10 次、冲击后 14 次决策都与 PAMS 一致，D 未推进当前 agent 的 RNG。[PAMS 测试](evidence/pams-packing.txt) · [事件记录](evidence/live-event.txt) | [3ef2298](https://github.com/DengJunxian/CoreOrder/commit/3ef229813355adf0e116b7704b08d0dd1b293703) |

## 运行环境与交付件

验证主机为 Windows x64，使用 CPython 3.12.13、NumPy 1.26.4、SciPy 1.14.1、tqdm 4.66.6、pytest 7.4.4、MSVC 19.44、pybind11 2.13.6。公共 fixture 原始采集平台为 macOS arm64。现场另使用 Python 3.12.14 对真实 PAMS 对象做独立重放。给定用例通过跨平台比较，跨平台的所有 FCN 输入仍需各自验证。

干净本地实现提交 `500a31afa6a05211992ad5834bc3eb75b53db68d` 与远端 D3 实现的 Git tree 同为 `edf3c521adb3334dbaf1a3c385c5f7fb4583496f`。本机 Git HTTPS 未配置写入凭据，本次由已获仓库写权限的 GitHub 连接发布相同文件树，因此远端提交使用平台生成的提交标识。复验包括 13 项 pytest、公共 fixture 的 B×D 串行回放、真实事件的 D×B 旁路回放，三条命令退出码均为 0。[复验日志](evidence/committed-replay.txt)

| 内容 | 交付位置 |
|---|---|
| 源码与核心接口 | [packing.py](../../../src/coreorder/packing.py) · [公共 ABI 的原生适配](../../../native/layout/abi.hpp) |
| 接入方法、依赖、复制次数、计时边界与复现命令 | [HANDOFF.md](HANDOFF.md) |
| 公共主控、D1 至 D3 原始阶段提示词、用户追加的团队协作指令 | [PROMPT_D1-D3.md](PROMPT_D1-D3.md) |
| 来源、许可证与论文方法素材 | [RESEARCH.md](RESEARCH.md) · [PAPER_NOTES.md](PAPER_NOTES.md) |
| 本机打包微基准 | 固定 PAMS 末态的 24 行批次，每种布局预热 4 次，24 个交替区组。AoS 中位数 331.00 µs/批，SoA 为 367.05 µs/批。两个布局输入均为 2688 B，metadata 均为 576 B。仅测量实时打包、视图创建与释放。[48 个原始时间与源码哈希](evidence/pack_micro.json) |

## 未完成和待集成

| 状态 | 依赖和责任人 | 验收方式 |
|---|---|---|
| INTEGRATION_PENDING | A 的候选 G0 为 `f867a4fb07c928f459fa8b6d3e84a95ee88b1742`。组长冻结主线公共 ABI、fixture 与 A3 的批次/原样本/回填调用；A、B 确认 D 接口。 | 用同一有序批次逐字段核对元数据和 TTL、检查空 agent 分组，在原生 runner 中复验 B 的两个布局入口。 |
| INTEGRATION_PENDING | B 串行实现 `f8d2be9f1391ac5e430112665efaff7bb844c507` 已实测。A/C 将正式 Taskflow executor 接入 B 的 binding，E 提供独立全系统比较。 | 由组长在 native-serial、workers 1/2/4、两布局与两种恢复模式运行订单、逐步状态与最终 RNG 验收，并对照未修改 PAMS。详见 [接入说明](HANDOFF.md)。 |
| NOT_RUN | G2 系统级验收、正式端到端实验、PMU 计数。E 和组长冻结实验协议后另行启动。 | 届时记录完整配置、种子、源码、计时边界与系统结果。D1–D3 工作到本次交付为止。 |
