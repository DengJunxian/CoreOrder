# B1 数值与布局探针

需要 Linux 或 WSL2、CPython 3.12、GCC C++17，以及下列固定源码树。路径可指向组内 `vendor/` 的 submodule，也可指向仓库外解压的固定 SHA 源码。运行前核对 checkout 的 `git rev-parse HEAD`，或从相应的固定提交下载源码快照。

| 参数 | 固定源 |
| --- | --- |
| `--pams-source` | `masanorihirano/pams@6cd53810103780770c5b5d6ee0069ccab9f4b358` |
| `--taskflow` | `taskflow/taskflow@816b4ad53b44196c88f409eb7b4a25a0e3bfdf42` |
| `--pybind11` | `pybind/pybind11@a2e59f0e7065404b44dfe92a28aca47ba1378dc4` |

在隔离的 Python 环境中，从 CoreOrder 根目录运行。

```bash
python3.12 -m venv /path/to/b1-venv
source /path/to/b1-venv/bin/activate
python -m pip install numpy==1.26.4 scipy==1.14.1 tqdm==4.66.6
python -B tests/native/b1/reproduce.py \
  --pams-source /path/to/pams \
  --taskflow /path/to/taskflow \
  --pybind11 /path/to/pybind11 \
  --output /path/to/new-b1-run
```

每次用新的输出目录。`probe.json` 保存标准输出中的逐项比较汇总。`abi.json` 保存 C++ 与 NumPy 的布局对照。`run.json` 保存实际命令、退出码、错误输出、环境与源码哈希。实验二进制留在输出目录。

`oracle.py` 提供独立的上游订单入口。`fcn_probe.cpp` 来自分发包的 EPL-1.0 研究探针，相关来源和许可见文件头及 `LICENSE`。数值探针采用 `N×16 double` 的诊断输入。计划 112 字节输入和 16 字节输出由 `abi_probe.cpp` 单独验证，后续 B2/B3 接入生产接口。
