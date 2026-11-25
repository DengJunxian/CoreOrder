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

## Run the serial baseline

Use the P01 virtual environment. These commands use distinct output directories
for the official upstream comparison and the CoreOrder run.

```sh
.venv/bin/python vendor/pams/samples/CI2002/main.py \
  --config vendor/pams/samples/CI2002/config.json --seed 42
.venv/bin/python -m coreorder.reference \
  --config configs/workloads/smoke.json --seed 42 --output results/reference-smoke
.venv/bin/python -m coreorder run --backend py-seq --book-restore upstream \
  --config configs/workloads/smoke.json --seed 42 --output results/py-seq-smoke
.venv/bin/python -m coreorder environment --output results/environment.json
```

`smoke.json` keeps the CI2002 Market and FCNAgent settings, reduces the agent
count to 24, and uses 20 warm-up steps and 60 trading steps. Each session
explicitly sets `maxNormalOrders=1` and `withPrint=false`. The unchanged
100-agent, 600-step upstream configuration stays under `vendor/pams` and
inherits the same order quota from PAMS.

Each run saves `workload.json` and `effective_config.json` byte-for-byte from
the supplied JSON. The run directory also contains the manifest, environment,
metrics, status, stdout/stderr, ordered trading events, per-market step
observations, initial and final accounts, final order books, and final RNG
state. Prices and cash in the observations use hexadecimal floats. The
reference calls `SequentialRunner.main()` directly. Both entries use the same
read-only observer. Times from these instrumented runs are diagnostic.

Existing output directories are protected. An unimplemented backend or
book-restore mode exits with status 2 and records `UNSUPPORTED`.

## Public interfaces and fixtures

See the [R4-v1 contract](docs/CONTRACT.md), [fixture provenance and replay](fixtures/README.md),
[team ownership](docs/TEAM.md), and [G0 candidate](docs/roles/A/G0_CANDIDATE.md).
The current serial runner also records full per-step account and logical book
snapshots, market history and RNG state.

`python -m coreorder validate --suite smoke --output results/validate-smoke` and
the corresponding `--suite g0` dispatch to E's independent validator. A checkout
without that implementation records BLOCKED and exits 3.
