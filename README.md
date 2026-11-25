# CoreOrder
Deterministic Multicore Execution and Cache-Aware Optimization for Multi-Agent Financial Market Simulation

## Rebuild the P01 foundation

Use Git, CPython 3.12 with development headers, and a C++17 compiler and linker.
On macOS, the Xcode Command Line Tools supply the compiler and SDK. The commands
below use a Unix shell from the repository root and install CMake into the
project virtual environment.

```sh
git submodule update --init --recursive --depth 1
git submodule status --recursive

python3.12 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.lock
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pip install --no-deps --no-build-isolation ./vendor/pams -e .
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q

.venv/bin/cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
  -DPython_EXECUTABLE="$PWD/.venv/bin/python"
.venv/bin/cmake --build build --config Release --parallel 2
.venv/bin/ctest --test-dir build -C Release --output-on-failure
```

Use a checkout containing the P01 commit. The Python tests verify the locked
Git submodules, retained licenses, and installed imports. CTest loads the
built pybind11 module and checks the output of two real Taskflow tasks.

For an environment record, capture `.venv/bin/python --version`,
`.venv/bin/python -m pip list --format=freeze`, `.venv/bin/cmake --version`,
`c++ --version`, `git --version`, and `git submodule status --recursive`.
See [upstream integration notes](docs/roles/A/UPSTREAM.md) and
[third-party notices](THIRD_PARTY_NOTICES.md).
