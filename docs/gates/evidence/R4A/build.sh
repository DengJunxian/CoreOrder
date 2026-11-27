#!/usr/bin/env bash
set -euo pipefail
root=$1
run() { printf '\n$'; printf ' %q' "$@"; printf '\n'; if "$@"; then printf 'exit=0\n'; else code=$?; printf 'exit=%s\n' "$code"; return "$code"; fi; }
cd "$root"
export GIT_TERMINAL_PROMPT=0
run git clone --branch codex/r3-correctness ./r3-source.bundle source
cd source
run test "$(git rev-parse HEAD)" = b5808b5383bfc170fcb972ee77f1c3c0eac5659f
run timeout --kill-after=5s 210s git submodule update --init --recursive --depth 1
run git submodule status --recursive
run test -z "$(git status --porcelain --ignore-submodules=none)"
run python3.12 --version
run python3.12 -m venv .venv
export PATH="$PWD/.venv/bin:$PATH"
run timeout --kill-after=5s 240s python -m pip install --only-binary=:all: -r requirements.lock
run timeout --kill-after=5s 240s python -m pip install --no-deps --no-build-isolation ./vendor/pams -e .
run python -m pip check
run c++ --version
run cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DPython_EXECUTABLE="$PWD/.venv/bin/python"
run timeout --kill-after=5s 180s cmake --build build --config Release --parallel 4
run sha256sum build/_coreorder_fcn*.so build/compile_commands.json
run ctest --test-dir build -C Release --output-on-failure
