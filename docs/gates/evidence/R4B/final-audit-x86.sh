#!/usr/bin/env bash
set -euo pipefail
root=$(realpath "$1")
cd "$root/source"
export PATH="$PWD/.venv/bin:$PATH" PYTHONPATH="$PWD:$PWD/build"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
mask=0,2,4,6,8,10,12,14
run() { printf '\n$'; printf ' %q' "$@"; printf '\n'; if "$@"; then printf 'exit=0\n'; else code=$?; printf 'exit=%s\n' "$code"; return "$code"; fi; }
for i in $(seq 1 1080); do
    if grep -Eq '^exit=[0-9]+$' "$root/v01.log" 2>/dev/null; then break; fi
    sleep 5
done
test -f "$root/V01/batch.json"
grep -Eq '^exit=[0-9]+$' "$root/v01.log"
run date -u --iso-8601=seconds
run taskset -c "$mask" python "$root/audit_batch.py" configs/experiments "$root/C01" "$root/c01-index.json"
run taskset -c "$mask" python "$root/audit_batch.py" "$root/approved" "$root/V01" "$root/v01-index.json"
if grep -q '^exit=0$' "$root/v01.log"; then
    run taskset -c "$mask" python "$root/replay_capture.py" --plan "$root/approved" --output "$root/replay-source" --seed 101 --v01 "$root/V01"
fi
run date -u --iso-8601=seconds
