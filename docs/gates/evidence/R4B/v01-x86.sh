#!/usr/bin/env bash
set -euo pipefail
root=$(realpath "$1")
source_sha=$2
plan=$(realpath "$3")
cd "$root/source"
export PATH="$PWD/.venv/bin:$PATH" PYTHONPATH="$PWD:$PWD/build"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
mask=0,2,4,6,8,10,12,14
for i in $(seq 1 420); do
    if grep -Eq '^exit=[0-9]+$' "$root/c01.log" 2>/dev/null; then
        break
    fi
    sleep 5
done
grep -q '^exit=0$' "$root/c01.log" || { printf 'C01 did not complete successfully\n'; exit 3; }
test "$(git rev-parse HEAD)" = "$source_sha"
test -z "$(git status --porcelain --ignore-submodules=none)"
taskset -c "$mask" python - "$root" "$plan" <<'PY'
import os
from pathlib import Path
import sys
from experiments.evidence import inspect_environment
from experiments.protocol import Protocol
from validation.io import read, write
root=Path(sys.argv[1])
approved=Protocol(Path(sys.argv[2]))
budget=read(root/"budget-preflight.json")["estimates"]["R4B_approved"]
assert not budget["rows_without_passing_proxy"] and budget["known_proxy_minutes"] <= 80
assert not approved.active
env,runtime=inspect_environment(approved, True)
previous=read(root/"C01/batch.json")["runtime"]
assert runtime==previous==read(root/"rehearsal/candidate-identity.json")
assert runtime["git_sha"]==approved.lock["primary_x86"]["code_sha"]
assert sorted(os.sched_getaffinity(0))==approved.lock["primary_x86"]["affinity"]["guest_cpus"]
write(root/"v01-preflight.json", {"runtime":runtime,"plan_id":approved.identity,"affinity":sorted(os.sched_getaffinity(0))})
PY
{
    date -u --iso-8601=seconds
    echo "taskset -c $mask python $root/replay_capture.py --plan $plan --output $root/replay-calibration --seed 11 --calibrate 3000"
    set +e
    taskset -c "$mask" python "$root/replay_capture.py" --plan "$plan" --output "$root/replay-calibration" --seed 11 --calibrate 3000
    echo exit=$?
    set -e
} </dev/null > "$root/replay-calibration.log" 2>&1
{
    date -u --iso-8601=seconds
    echo "taskset -c $mask python -m experiments.run --plan $plan --stage V01 --budget-seconds 4800 --output $root/V01"
    ulimit -v 7340032
    set +e
    /usr/bin/time -v taskset -c "$mask" python -m experiments.run --plan "$plan" --stage V01 --budget-seconds 4800 --output "$root/V01"
    echo exit=$?
    set -e
    date -u --iso-8601=seconds
} </dev/null > "$root/v01.log" 2>&1
