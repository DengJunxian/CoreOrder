#!/bin/bash
# Run from the root of a built CoreOrder checkout. Use a fresh output directory.
set -euo pipefail

if [ "$#" -ne 1 ]; then
  printf '%s\n' 'Usage: bash scripts/verify-semantics.sh NEW_OUTPUT_DIRECTORY' >&2
  exit 2
fi
output="$1"
mkdir -p "$(dirname "$output")"
mkdir "$output"
output="$(cd "$output" && pwd)"
python="$PWD/.venv/bin/python"
export PYTHONPATH="$PWD/build"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
config=configs/workloads/native-serial-normal.json
seed=42

git rev-parse HEAD > "$output/commit.txt"
git submodule status --recursive > "$output/submodules.txt"
"$python" -m pip check > "$output/pip-check.txt"
"$python" -m coreorder environment --output "$output/environment.json"
"$python" -m coreorder validate --suite smoke --output "$output/smoke"
"$python" -m validation collect --config "$config" --pams-root vendor/pams \
  --seed "$seed" --output "$output/reference.json.gz" > "$output/oracle.log"

run() {
  local label=$1
  shift
  "$python" -m coreorder run --config "$config" --seed "$seed" --output "$output/$label" \
    --validation-trace "$@"
  "$python" -m validation compare --reference "$output/reference.json.gz" \
    --candidate "$output/$label/validation-trace.json.gz" \
    --bundle "$output/$label-first-divergence" | tee "$output/$label-comparison.json"
}

run py-upstream --backend py-seq --book-restore upstream
run py-incremental --backend py-seq --book-restore incremental
run serial-aos --backend native-serial --layout aos --book-restore incremental
run parallel-soa --backend native-parallel --layout soa --workers 2 \
  --grain 2 --schedule static --book-restore incremental

for workers in 1 4; do
  run "parallel-soa-w$workers" --backend native-parallel --layout soa --workers "$workers" --grain 2 --schedule static --book-restore incremental
done
