#!/usr/bin/env bash
set -euo pipefail
root=$1
sha=$2
previous=$HOME/coreorder-r4a-gTl3K1Uz/source
run() { printf '\n$'; printf ' %q' "$@"; printf '\n'; if "$@"; then printf 'exit=0\n'; else code=$?; printf 'exit=%s\n' "$code"; return "$code"; fi; }
cd "$root"
run git clone --branch codex/r4b-freeze ./r4b-source.bundle source
cd source
run test "$(git rev-parse HEAD)" = "$sha"
for vendor in pams taskflow pybind11; do
    run git config "submodule.vendor/$vendor.url" "$previous/vendor/$vendor"
done
run git -c protocol.file.allow=always submodule update --init --recursive
run git submodule status --recursive
run test -z "$(git status --porcelain --ignore-submodules=none)"
run python3.12 -m venv .venv
export PATH="$PWD/.venv/bin:$PATH"
run timeout --kill-after=5s 240s python -m pip install --only-binary=:all: -r requirements.lock
run timeout --kill-after=5s 240s python -m pip install --no-deps --no-build-isolation ./vendor/pams -e .
run python -m pip check
run c++ --version
run cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DPython_EXECUTABLE="$PWD/.venv/bin/python"
run timeout --kill-after=5s 180s cmake --build build --config Release --parallel 4
run sha256sum build/_coreorder_fcn*.so build/compile_commands.json
export PYTHONPATH="$PWD:$PWD/build"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
run ctest --test-dir build -C Release --output-on-failure
run taskset -c 0,2,4,6,8,10,12,14 python -m pytest -q tests/platform/test_checkpoint_stream.py tests/platform/test_measurement_modes.py tests/platform/test_experiment_pipeline.py
run python -m experiments.run --stage check
