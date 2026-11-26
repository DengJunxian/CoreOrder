#!/usr/bin/env bash
# On the authorized target, read the existing R4B batches and write a separate archive.
set -euo pipefail
root=$(realpath "${1:?Usage: reseal-x86.sh EXISTING_R4B_DIR}")
dest=$(mktemp -d "$HOME/coreorder-r8-archive.XXXXXX")
printf 'archive_directory=%s\n' "$dest"
run() {
    printf '\n$'; printf ' %q' "$@"; printf '\n'
    if "$@"; then printf 'exit=0\n'; else code=$?; printf 'exit=%s\n' "$code"; return "$code"; fi
}
cd "$root/source"
export PATH="$PWD/.venv/bin:$PATH" PYTHONPATH="$PWD:$PWD/build"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
run date -u --iso-8601=seconds
run git rev-parse HEAD
run git submodule status --recursive
test -z "$(git status --porcelain --ignore-submodules=none)"
run sha256sum build/_coreorder_fcn*.so
run taskset -c 0,2,4,6,8,10,12,14 python "$root/audit_batch.py" configs/experiments "$root/C01" "$dest/c01-index.json"
run taskset -c 0,2,4,6,8,10,12,14 python "$root/audit_batch.py" "$root/approved" "$root/V01" "$dest/v01-index.json"
run cmp "$root/c01-index.json" "$dest/c01-index.json"
run cmp "$root/v01-index.json" "$dest/v01-index.json"
run sha256sum "$dest/c01-index.json" "$dest/v01-index.json"
run python -m experiments.run --stage check --plan "$root/approved"
python - "$dest" <<'PY'
import json
import sys
from collections import Counter
from pathlib import Path

target = Path(sys.argv[1])
plans = {path for root in Path.home().glob("coreorder-*") if root != target
         for path in root.glob("**/batch.json") if "vendor" not in path.parts}
claims = list((Path.home()/".coreorder/execution").glob("**/*.json"))
formal = []
for path in sorted(plans):
    info = json.loads(path.read_bytes())
    scope = info.get("scope")
    print(scope, info.get("stage"), path.relative_to(Path.home()))
    if scope in ("formal-timing", "formal-diagnostic"):
        formal.append(str(path))
assert not formal and not claims
print("formal_batch_count=0 formal_claim_count=0")
PY
cd "$root"
# The target retains C01/V01 and diagnostics; a single-copy archive can be restored independently.
printf '\n$ tar -cf - C01 V01 approved replay-calibration replay-source target-g0 | gzip -1\n'
tar -cf - C01 V01 approved replay-calibration replay-source target-g0 | gzip -1 > "$dest/target-validation-and-pilots.tar.gz"
printf 'exit=0\n'
run gzip -t "$dest/target-validation-and-pilots.tar.gz"
run tar -dzf "$dest/target-validation-and-pilots.tar.gz"
cd "$dest"
sha256sum target-validation-and-pilots.tar.gz c01-index.json v01-index.json > SHA256SUMS
run sha256sum -c SHA256SUMS
run stat -c '%s %n' target-validation-and-pilots.tar.gz
run date -u --iso-8601=seconds
