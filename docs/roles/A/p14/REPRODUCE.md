# 平台构建与代表性复现

本文的本地验证对象是 `1027ee892f77963fbebc72839f322157be2821f8`，其中实际生产路径等同 `92f8bbf08da514dcb24e27b6a815d3947c352798`。P14 的文档提交晚于该验证对象。P11 原始运行 checkout 是 `3c344f765c6ff288abad2faa6081c921f0ee0f36`。正式 G3 生效 SHA 为空。 [版本锁](../../../../UPSTREAM.lock.json) · [G3 状态](../../../gates/G3.md)

## 获得源码

公开复验使用 GitHub 的 `codex/research-candidate` 分支。记录当前提交和完整 submodule SHA。P14 本机归档的运行身份见上文。

```sh
git clone --branch codex/research-candidate https://github.com/DengJunxian/CoreOrder.git CoreOrder-repro
cd CoreOrder-repro
git submodule update --init --recursive --depth 1
git submodule status --recursive
git status --short
```

若 shallow 获取受到远端限制，执行一次不带 `--depth` 的同一命令，最终仍以仓库记录的 gitlink 为准。固定 PAMS、Taskflow 与 pybind11 的许可证保留在 `licenses/`，PAMS 版本号 0.3.0 与官方同名 tag 的 Git 历史需通过 SHA 区分。 [许可、来源与衍生说明](../../../../THIRD_PARTY_NOTICES.md)

## 干净构建、smoke 与两市场对照

需要 CPython 3.12、C++17 编译器和 Python 开发头文件。macOS 可用 Xcode Command Line Tools，Linux 可用支持严格浮点参数的 GCC 或 Clang。下列步骤从 checkout 根目录运行，输出使用新目录。网络仅用于固定上游及锁定 wheel。 [项目 README](../../../../README.md)

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.lock
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pip install \
  --no-deps --no-build-isolation ./vendor/pams -e .
.venv/bin/python -m pip check
.venv/bin/cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DPython_EXECUTABLE="$PWD/.venv/bin/python"
.venv/bin/cmake --build build --config Release --parallel 2
.venv/bin/ctest --test-dir build -C Release --output-on-failure
PYTHONPATH="$PWD/build" .venv/bin/python -m pytest -q
bash docs/roles/A/p14/reproduce.sh "$PWD/results/p14-functional"
```

脚本先跑 E1 smoke，再从同一 JSON 和 seed 42 采集固定 PAMS 的独立轨迹。候选依次为 py-seq/upstream、py-seq/incremental、native-serial/AoS/incremental 和 native-parallel/SoA/incremental，最后一组为 2 workers、static、grain 2。代表配置含两市场、normal margin、零名额 session、稀疏访问、HFT 和基本面冲击。命令保存命令状态、原始和有效配置、事件、每步状态、汇总及 RNG，出现首差异会保存 E 可重放目录并返回非零。输出用于功能复现与现场展示。 [代表配置](../../../../configs/workloads/native-serial-normal.json) · [复现脚本](reproduce.sh)

## 本机实际结果

在 Apple M5、macOS 27.0 ARM64、CPython 3.12.13、Apple Clang 21 上，从本地候选仓库作 `git clone --no-local`，随后从三个上游 URL 获取固定 gitlink。依据实际 Release 编译数据库，原生翻译单元使用 `-O3 -fno-fast-math -ffp-contract=off`。锁定 wheel 通过 `pip check`，三份保留的第三方许可证与固定上游逐字节一致。CTest **2/2**，pytest **92 passed、39 warnings**，E1 smoke **PASS**。原生扩展实际加载，SHA-256 为 `b80814cff55404fd75c69f774674ec9152ad95cc935d68eb8a95f852847377d1`。 [机器可读回执](reproduction-receipt.json)

代表配置四路均通过 E 的 `events`、`steps`、`initial`、`final`、`rng` 结构差分。原版记录 184 条事件，含 89 条订单、28 次成交、25 次到期。首轮复现脚本遗漏 `--validation-trace`，比较因轨迹文件不存在退出；补齐参数后用新目录完整重跑。本机原始证据位于 P14 工作树的 `results/reproduction/p14/`，包含 `rebuild.log`、`representative.log`、`representative-rerun.log` 和完整 `representative-rerun/`。 [run ID、哈希和结果](reproduction-receipt.json)

## E 的另一设备回执

当前另一台物理设备 **NOT_RUN**。E 可在获准设备上按上述说明克隆并运行脚本，回收源码与 gitlink、系统和 CPU、Python/编译器、wheel lock、实际扩展 SHA、四条结构比较及原始记录。不同平台可比较语义与本机内部的配对，性能量不能跨架构合并。即使另一机小配置通过，公共 FINAL 中的正式配置复现还依赖有效 G3、V01 及相应原始数据。 [组长 G2](../../../gates/G2.md) · [冻结准入](../../../gates/G3.md)
