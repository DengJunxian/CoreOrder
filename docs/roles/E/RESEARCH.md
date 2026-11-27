# 成员 E 研究记录

GitHub推送准备补记：完整离线交付分支纳入了大量可再生轨迹；按common/07_GitHub_Manual第4、8节要求另建e/03-github-delivery轻量分支，原分支/历史/数据均保留，完整bundle单独归档。源码、测试、实验模板均按SHA256核对与原交付一致。原日志和PASS结果没有改签；此新分支仍需待组长统一集成，正式性能未运行。当前步骤仅准备本地提交与推送教程，不执行远端写入。

2026-11-25，基线 `e2492a4b8317c6674918b13470b577f4d6f8675d`，不是 G0。
远端 main 仅 README/gitignore；未合入其他成员分支。Git HTTPS clone 两次连接重置；改为官方 codeload 归档和 API 原始 signed commit，重建对象后验证 tree 和 commit SHA 完全一致。不是新造基线提交。代码与分发包分离在 CoreOrder 子目录。

固定源码研究：PAMS sequential.py `_collect_orders_from_normal_agents` 按非空 agent 列表计 M，`_handle_orders` 再由 runner Random.sample 排序，不能按 ID 排序；`_process_order` 使用原撮合与账户更新；`_iterate_market_updates` 的 MarketStepEndLog 在 after-step hook **之前**，不能把它当完整 step。故观察点选 simulator 批量时间推进后，最终另捕获。
`logs/base.py` 延迟日志持有对象引用，故写入时编码而非 process 时读取可变状态。
`order.py:_gt_lt` 原比较器定义逻辑簿，不比较物理 heap 数组。`order_book.py` 的 expire_time_list 列表次序影响日志，不可排序。
`simulator.py:_update_agents_for_execution` 无费现金双向更新，可为负；固定版本同时有费用字段，守恒工具会显式拒绝未支持的有费检验。
`fundamentals.py` 同时持有 Python Random 与 NumPy Generator；只收集 agent RNG 不足。
`agent_parallel.py` 已有受约束的并行批次、进程序列化与 RNG 同步，均为上游贡献。
`fcn_agent.py` fixed 访问市场调用一次 gauss，normal 即使空单也调用第二次；不可访问市场不调用。

E1 首次测试：1 pass/5 fail，原因是 Windows 默认 GBK 读取包含中文的 UTF-8 schema。定向修复1：显式 UTF-8，不更改 schema 字段或金融逻辑；复测6 pass。原失败日志保留在 results/acceptance/E1/attempt1。

方法来源（2026-11-25核读）：

- [PAMS 固定源码](https://github.com/masanorihirano/pams/tree/6cd53810103780770c5b5d6ee0069ccab9f4b358)，EPL-1.0；原金融算法完全继承。新增 E 工具采用 EPL-1.0，原文副本见 licenses。
- [Kalibera–Jones 2013](https://kar.kent.ac.uk/33611/)，区分构建/进程/迭代等重复层级和不确定性；本项目采用 R4 的 seed 层级及区组方案，不把三次计时重复称三个市场样本，不宣称本工作发明分层统计。
- [perf stat 手册](https://man7.org/linux/man-pages/man1/perf-stat.1.html)，计数器按实际 scope 与运行比例报告；当前 Windows 开发未采 PMU。
- [Cachegrind 官方手册](https://valgrind.org/docs/manual/cg-manual.html)，模拟 cache 模型较基础，与现代硬件行为有边界；不把模拟计数称实测 LLC。

环境：隔离 CPython 3.12.14、NumPy1.26.4/SciPy1.14.1/tqdm4.66.6/pytest7.4.4；完整传递依赖锁附后。PATH 的 MSYS2 Python 无 pip/数值依赖，未修改该全局环境。

后续每阶段在此追加真实测试、故障和未完成边界。正式性能 E4/E5 未授权启动。

E2：增加已知故障：事件交换、价格nextafter一位、全空订单情况下少采一次normal gauss。最后一种故障的事件轨迹完全相同，但逐step RNG发生分歧，说明仅看订单或价格曲线不足。增加无费总现金、总证券、成交订单剩余量/最终簿及账户重放一致性检查，路径比较仍exact。
E2测试首轮12 pass/1 fail/1 error：测试误以为final/rng与顶层rng深拷贝后不共享（实际仍共享，所以更早在final捕获）；pytest默认临时目录不可访问。定向修复1：断言具体RNG路径，临时目录移入工作区；漏建父目录导致13 pass/1 error。定向修复2：显式创建.cache，14 pass。两轮后问题解决，所有失败日志保留。
真实上游py-thread与py-process代表小配置均同oracle一致，进程模式采用spawn，30秒预算，未将其结果外推为完整G2。A2堆与B/D原生binding不存在，未自行实现。

E3：12类×5seed×seq/thread完整回归，60对三层结构及双方不变量PASS。首轮在mixed-empty遇到空asset_volumes的合法编码{}，守恒工具误读为有map键。定向修复1：空字典返回空持仓；补无访问agent回归，第二个run目录120次全通过；首轮81个trace保留。
定向簿测试真实调用原_process_order/_execution/账户更新，含实际成交；没有复制堆恢复实现。normal场景seed101实际6笔成交，mixed-empty实际1笔成交；普通fixed短fixture未必发生成交，不能说每配置都覆盖撮合。
补预填gauss缓存、多市场、M0/M1跳过agent RNG、负现金合法性；累计31 tests通过。超时测试发现只调用taskkill时沙箱限制可使sleep继续10秒，补直接owned-process kill及限时pipe回收，并增加实际elapsed<5秒断言；测试总耗时约3秒。进程树无法确认清理时记录明确cleanup错误，不承诺当前Windows工具已可正式采数。
开发验证器微基准：46事件、7检查点、规范JSON1,837,454字节，预加载两个独立结构、warmup1、技术重复7；第一次开发记录median33.4538ms。dirty开发数据仅描述工具成本，不进入正式图，不解释CPU cache或系统收益。最终干净源码还会复核该工具。
最后复核远端main仍为初始化SHA，未同步其他成员分支。为组长新增R4 manifest/metrics/status输出（validation模式所有时间null+原因），正式摘要必须同时有真实正simulation时间，避免仅PASS标签放行缺测。
新增gate完整schema正例测试时，错误地用tests.differential导入测试辅助函数，被上游tests包遮蔽，30 pass/1 fail；定向修复1使用pytest实际加载的本地test_e1模块，未修改上游或根目录。该失败日志同样保留。

最终源码52260be7cca066b896de7c7f266552add93a82cb在干净树复核：31 tests、120个完整trace、120套R4验证记录、normal seed101进程路径（6笔实际成交）、pip check均exit0/dirty=false。微基准再次保存7个原始样本，median33.4834ms；依旧不是正式系统性能。产物先写仓库外.deliveries/clean-verification以保持验证时源树干净，再逐字节复制入results/acceptance/E3/clean-52260be，原文件不改写。最终证据提交不改变源码，完成后停止E1–E3。
