# P01 上游接入

基线为 CoreOrder `e2492a4b8317c6674918b13470b577f4d6f8675d`，本地阶段分支为 `a/01-foundation`。上游 Git URL、版本、全 SHA、检出路径与许可证记录在 [UPSTREAM.lock.json](../../../UPSTREAM.lock.json)。[第三方许可清单](../../../THIRD_PARTY_NOTICES.md) 记录副本与工具依赖的出处。PAMS 的 `0.3.0` 是固定提交的包版本，安装输入为检出后的 `vendor/pams`。

- PAMS 以普通 wheel 安装到项目隔离环境。`uv_build` 来自固定 PAMS 提交的构建要求，与应用依赖及 CMake 一起由 [requirements.lock](../../../requirements.lock) 固定。关闭 pip 构建隔离时，构建用虚拟环境的 `bin` 须在 PATH 前面，以便 Python shim 找到锁定的 `uv-build`。
- Taskflow 以原头文件接入测试目标，pybind11 以原 CMake 子目录建立测试扩展。扩展以 C++17 编译，释放 GIL 后让 Taskflow 的两个任务各写一个输出槽，等待任务完成后断言总和为 42。该扩展仅用于 CTest 工具链验证。
- 回归检查核对 `.gitmodules` URL、父仓库 gitlink、上游 HEAD、工作树与原许可证，另核对安装的 PAMS 来源和 `SequentialRunner` 导入。

按 [README](../../../README.md#rebuild-the-p01-foundation) 从仓库根目录重建。实际命令、依赖版本、编译参数与退出状态见 [P01 日志](evidence/P01.txt)。接入修改均在 CoreOrder，三个 vendor 工作树保持原样。
