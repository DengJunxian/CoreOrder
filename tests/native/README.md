# B 数值核和绑定独立复现

在 Linux 或 WSL2 的 LF 检出中运行。`git submodule status --recursive` 应匹配 `UPSTREAM.lock.json`。按候选基线使用 CPython 3.12 与 GCC 或 Clang，安装锁中的依赖。用原始 LF 检出保留 PAMS 源码和公共 fixture 的哈希。

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip check
cmake -S tests/native -B build-fcn -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DPython_EXECUTABLE="$VIRTUAL_ENV/bin/python"
cmake --build build-fcn --parallel
ctest --test-dir build-fcn --output-on-failure
export PYTHONPATH="$PWD/build-fcn:$PWD/src:$PWD/vendor/pams"
COREORDER_FCN_TEST_MODULE=_coreorder_fcn python -B -m pytest -q -s tests/native/test_fcn.py
COREORDER_FCN_TEST_MODULE=_coreorder_fcn_test python -B -m pytest -q -s tests/native/test_fcn.py
python -B tests/native/microbench.py
```

基础工作流在编译前运行仓库级 pytest，此时会跳过尚未构建的原生测试套件。上面的两条定向命令显式指定待测模块，模块缺失或加载失败都会报错。第二套 pytest 使用独立的 C 测试替身，覆盖工厂生命周期、两种布局和 1/2/4 workers 的调用结果。两模块分别在独立 Python 进程中导入。跨主机复放诊断报告高斯浮点差异，逐位验收使用本机实际原版 PAMS 调用，以及公共样本已经捕获的 `z_noise/z_margin`。

在本次 GCC/WSL2 环境，ASan 和 UBSan 验证可独立运行。

```sh
cmake -S tests/native -B build-fcn-sanitize -DCMAKE_BUILD_TYPE=Debug \
  -DCOREORDER_FCN_SANITIZE=ON -DPython_EXECUTABLE="$VIRTUAL_ENV/bin/python"
cmake --build build-fcn-sanitize --parallel
ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 \
  ctest --test-dir build-fcn-sanitize --output-on-failure
LD_PRELOAD="$(g++ -print-file-name=libasan.so):$(g++ -print-file-name=libstdc++.so)" \
  ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 \
  PYTHONPATH="$PWD/build-fcn-sanitize:$PWD/src:$PWD/vendor/pams" \
  COREORDER_FCN_TEST_MODULE=_coreorder_fcn_test python -B -m pytest -q -s tests/native/test_fcn.py
```
