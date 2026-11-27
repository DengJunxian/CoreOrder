# CoreOrder
Deterministic Multicore Execution and Cache-Aware Optimization for Multi-Agent Financial Market Simulation

**Final project delivery.** CoreOrder preserves the PAMS trajectory while
changing heap restoration, native execution and memory layout. The target
passed 420 C01 and 145 V01 correctness attempts. The group-leader-authorized
independent campaign completed 465 timing measurements and 79 mechanism
launches, with all 375 planned pairs. The original two-reviewer G3 remains
inactive.

Matched W2-H simulation speedups were 16.704× for heap-only, 13.266× for
four-worker AoS and 13.143× for four-worker SoA against stock PAMS.

[Experiment results](docs/results/README.md) · [Reproduction](docs/REPRODUCE.md) · [Final audit](docs/gates/FINAL.md)

## Build and test the pinned system

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

.venv/bin/cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
  -DPython_EXECUTABLE="$PWD/.venv/bin/python"
.venv/bin/cmake --build build --config Release --parallel 2
.venv/bin/ctest --test-dir build -C Release --output-on-failure
PYTHONPATH="$PWD/build" .venv/bin/python -m pytest -q
```

The Python checks include the production runners and the independent validator.
CTest covers the compiled extension, Taskflow ranges and determinism, the
AoS/SoA ABI, and event-refresh packing. See the [pinned identities](UPSTREAM.lock.json).

For an environment record, capture `.venv/bin/python --version`,
`.venv/bin/python -m pip list --format=freeze`, `.venv/bin/cmake --version`,
`c++ --version`, `git --version`, and `git submodule status --recursive`.
See [upstream integration notes](docs/roles/A/UPSTREAM.md) and
[third-party notices](THIRD_PARTY_NOTICES.md).

## Run the serial baseline

Use the project virtual environment. These commands use distinct output directories
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
same FCN kernel. The process baseline uses PAMS with spawn. Validation and
legacy diagnostics record serialized dispatch bytes in `process_copy.json`.
The native modes accept
exact PAMS FCNAgent decisions and preserve original order processing and the
MarketMakerAgent HFT path. See the [capability matrix and evidence](docs/roles/A/INTEGRATION.md).

## Select a measurement mode

Use `run --mode validation` for full traces and the independent PAMS
comparison, `run --mode timing` for the complete low-overhead simulation,
`run --mode profile` for stage and function spans, or
`run --mode pmu --pmu-event EVENT` for Linux perf counters. In profile mode,
add `--cprofile` to collect full Python function statistics in a separate run.
Omitting `--mode` retains the legacy diagnostic artifacts.

```sh
PYTHONPATH="$PWD/build" .venv/bin/python -m coreorder run --mode timing \
  --backend native-parallel --workers 2 --layout soa --book-restore incremental \
  --config configs/workloads/native-serial-normal.json --seed 11 \
  --output results/r2a-timing-smoke
```

Read `setup_s`, `simulation_s` and `process_wall_s` in `metrics.json`.
The parent records the executed command, exit status and wall time under
`launch/`. Timing includes business work, worker waits and executor shutdown.
The final state and complete RNG snapshot are serialized after the simulation
timer stops. The example is a development check. The [original G3](docs/gates/G3.md)
remains inactive. The [completed independent study](docs/gates/FINAL.md)
used a separate authorized lock. See the [measurement contract](docs/CONTRACT.md#运行模式与计时边界)
and the [R2A verification record](docs/gates/evidence/R2A/README.md).

## Run a frozen experiment plan

Use `python -m experiments.run --plan configs/experiments/r4b --stage check` to
verify the reviewed schedule and read its G3 status.
The pilot runs independent PAMS validation, binds each timing run to its
receipt and writes sealed raw records. Use `python -m analysis.report` for
paired statistics and optional PDF/PNG figures. The
[experiment guide](docs/EXPERIMENTS.md) covers development runs, resume,
budgets and formal G3 admission.

## Public interfaces and fixtures

See the [R4-v1 contract](docs/CONTRACT.md), [fixture provenance and replay](fixtures/README.md),
and [team ownership](docs/TEAM.md).
Validation and legacy diagnostics record per-step account and logical book
snapshots, market history and RNG state.

`python -m coreorder validate --suite smoke --output results/validate-smoke` and
the corresponding `--suite g0` run E's independent comparison against fixed PAMS.
The smoke suite uses the short CI2002 workload at seed 42. G0 also runs the
fundamental-shock and short-expiration workload. The output preserves both traces,
the comparison, and the status receipt. On divergence, it also saves a replay bundle.

## Reproduce the system

The [final project audit](docs/gates/FINAL.md) maps the published source to the
measured runtime, correctness checks and experimental data.

Use the [six-configuration semantic check](docs/REPRODUCE.md) with an already built checkout. The CLI accepts `validate --suite smoke`, `g0`,
`g1`, and `g2` for local correctness checks. The G1 reproduction script
retrieves the pinned original E tree needed by its historical heap checks. Unsupported native inputs
fail explicitly. Choose `py-seq` before a run to use the upstream Python path.
