#!/bin/bash
# Invoke from a built CoreOrder checkout. The output directory must be new.
set -euo pipefail

if [ "$#" -ne 1 ]; then
  printf '%s\n' 'Usage: bash demo.sh NEW_OUTPUT_DIRECTORY' >&2
  exit 2
fi
output="$1"
config=configs/workloads/native-serial-normal.json
seed=42
python="$PWD/.venv/bin/python"
export PYTHONPATH="$PWD/build"

bash docs/roles/A/p14/reproduce.sh "$output"
for workers in 1 4; do
  label="parallel-soa-w$workers"
  "$python" -m coreorder run --config "$config" --seed "$seed" \
    --backend native-parallel --book-restore incremental --layout soa \
    --workers "$workers" --grain 2 --schedule static --validation-trace \
    --output "$output/$label"
  "$python" -m validation compare --reference "$output/reference.json.gz" \
    --candidate "$output/$label/validation-trace.json.gz" \
    --bundle "$output/$label-first-divergence" | tee "$output/$label-comparison.json"
done
