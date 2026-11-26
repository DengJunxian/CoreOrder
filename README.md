# CoreOrder
Deterministic Multicore Execution and Cache-Aware Optimization for Multi-Agent Financial Market Simulation

**Research candidate · FINAL blocked.** The candidate includes the integrated
PAMS runners, incremental book restoration, native FCN execution, AoS and SoA
layouts, and independent functional comparisons. Formal H01/E05 and hardware
PMU measurements are pending. The included performance figures come from the
Apple M5 pilot. See the [candidate status and provenance](docs/PUBLIC_CANDIDATE.md)
and the [FINAL audit](docs/gates/FINAL.md).

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
.venv/bin/python -m coreorder run --backend py-seq --book-restore incremental \
  --config configs/workloads/smoke.json --seed 42 --output results/py-seq-heap-smoke
.venv/bin/python -m coreorder environment --output results/environment.json
```

`smoke.json` keeps the CI2002 Market and FCNAgent settings, reduces the agent
count to 24, and uses 20 warm-up steps and 60 trading steps. Each session
explicitly sets `maxNormalOrders=1` and `withPrint=false`. The unchanged
100-agent, 600-step upstream configuration stays under `vendor/pams` and
inherits the same order quota from PAMS.

Each run saves the supplied JSON verbatim as `workload.json`. In upstream mode,
`effective_config.json` is identical to that input. Incremental mode records the
effective configuration with ordinary market groups selecting `CoreOrderMarket`.
The run directory also contains the manifest, environment,
metrics, status, stdout/stderr, ordered trading events, per-market step
observations, initial and final accounts, final order books, and final RNG
state. Prices and cash in the observations use hexadecimal floats. The
reference calls `SequentialRunner.main()` directly. Both entries use the same
read-only observer. Times from these instrumented runs are diagnostic.

Existing output directories are protected. An unsupported backend or market
class for incremental restore exits with status 2 and records `UNSUPPORTED`.
`--heap-diagnostics` and `--count-heap-comparisons` are independent, optional
flags. See the [heap method and validation evidence](docs/roles/A/HEAP_METHOD.md).

## Run the integrated backends

Build the Release extension above for native runs and add its directory to
`PYTHONPATH`.

```sh
PYTHONPATH="$PWD/build" .venv/bin/python -m coreorder run \
  --backend native-parallel --workers 4 --layout soa --book-restore incremental \
  --grain 2 --schedule dynamic --config configs/workloads/native-serial-normal.json \
  --seed 42 --output results/native-parallel
PYTHONPATH="$PWD/build" .venv/bin/python -m coreorder validate --suite g2 \
  --output results/validate-g2-candidate
```

The CLI exposes `py-seq`, `py-thread`, `py-process`, `native-serial` and
`native-parallel`. Both native modes support AoS and SoA, and both use the
same FCN kernel. The process baseline uses PAMS with spawn and records actual
serialized dispatch bytes in `process_copy.json`. The native modes accept
exact PAMS FCNAgent decisions and preserve original order processing and the
MarketMakerAgent HFT path. See the [capability matrix and evidence](docs/roles/A/INTEGRATION.md).

## Public interfaces and fixtures

See the [R4-v1 contract](docs/CONTRACT.md), [fixture provenance and replay](fixtures/README.md),
[team ownership](docs/TEAM.md), and [G0 candidate](docs/roles/A/G0_CANDIDATE.md).
The current serial runner also records full per-step account and logical book
snapshots, market history and RNG state.

`python -m coreorder validate --suite smoke --output results/validate-smoke` and
the corresponding `--suite g0` run E's independent comparison against fixed PAMS.
The smoke suite uses the short CI2002 workload at seed 42. G0 also runs the
fundamental-shock and short-expiration workload. The output preserves both traces,
the comparison, and the status receipt. On divergence, it also saves a replay bundle.

## Review and reproduce the local candidate

The [reproduction guide](docs/roles/A/p14/REPRODUCE.md) gives the pinned
clean-clone build and representative small-market comparison. The
[FINAL audit](docs/gates/FINAL.md) records the five-backend capability scope,
the actual gate status, and the remaining experimental and release requirements.

Use the [three-run demo procedure](docs/gates/evidence/P15/DEMO.md) with an
already built checkout. The CLI currently accepts `validate --suite smoke`,
`g0`, and `g2`. Unsupported native inputs fail explicitly. Choose
`py-seq` before a run to use the upstream Python path. The automatic
whole-run fallback option and the formal experiment runner are pending.
