#!/usr/bin/env bash
# Rebuild the tested production commit from a fresh clone.
set -euo pipefail
repo=${1:?Usage: reproduce.sh SOURCE_REPOSITORY NEW_DIRECTORY [LOCKED_UPSTREAM_CHECKOUT]}
root=${2:?Specify a new output directory}
vendor_cache=${3:-}
tested=58ec5764c21833142c50abacd9e2302404ffdb06
member_e=b05d5555fa5cc756a91ab61c644e797ca227c26f
run() {
    printf '\n$'; printf ' %q' "$@"; printf '\n'
    if "$@"; then printf 'exit=0\n'; else code=$?; printf 'exit=%s\n' "$code"; return "$code"; fi
}
run mkdir "$root"
root=$(cd "$root" && pwd)
run git clone --no-local --no-checkout "$repo" "$root/source"
cd "$root/source"
run git checkout --detach "$tested"
# The historical G1 scripts read the original E tree by SHA.
member_ref=refs/heads/e/03-github-delivery
if ! git ls-remote --exit-code "$repo" "$member_ref" >/dev/null; then
    member_ref=refs/remotes/origin/e/03-github-delivery
fi
run git fetch --no-tags "$repo" "$member_ref"
run test "$(git rev-parse FETCH_HEAD)" = "$member_e"
run git update-ref refs/coreorder/member-e "$member_e"
if [ -n "$vendor_cache" ]; then
    for name in pams taskflow pybind11; do
        run git config "submodule.vendor/$name.url" "$vendor_cache/vendor/$name"
    done
    run git -c protocol.file.allow=always submodule update --init --recursive
else
    run git submodule update --init --recursive --depth 1
fi
run git submodule status --recursive
run git status --short
test -z "$(git status --porcelain --ignore-submodules=none)"
run python3.12 -m venv .venv
export PATH="$PWD/.venv/bin:$PATH"
run python -m pip install --only-binary=:all: -r requirements.lock
run python -m pip install --no-deps --no-build-isolation ./vendor/pams -e .
run python -m pip check
run python --version
run c++ --version
run cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DPython_EXECUTABLE="$PWD/.venv/bin/python"
run cmake --build build --config Release --parallel 4
run shasum -a 256 build/_coreorder_fcn*.so build/compile_commands.json
export PYTHONPATH="$PWD/build" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
run ctest --test-dir build -C Release --output-on-failure
run python -m pytest -q -p no:cacheprovider
run python -m coreorder validate --suite g0 --output "$root/g0"
run python -m coreorder validate --suite g1 --output "$root/g1"
run python -m coreorder validate --suite g2 --output "$root/g2"
run bash docs/gates/evidence/P15/demo.sh "$root/demo"
run shasum -a 256 "$root/demo/"*-comparison.json "$root/demo/environment.json"
run git status --short
test -z "$(git status --porcelain --ignore-submodules=none)"
