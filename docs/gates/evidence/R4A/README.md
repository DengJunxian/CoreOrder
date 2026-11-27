# R4A evidence

Measured source SHA is `b5808b5383bfc170fcb972ee77f1c3c0eac5659f` on the target. These files cover development qualification, P01 and bounded follow-ups. The R4A evidence commit and the measured source SHA identify different artifacts.

## Evidence layout

- `build.log` and `compile_commands.json` record the clean, pinned Release build and the production extension checksum.
- `host-linux.log`, `host-windows-encoded.log` and `cpuid.log` record the host and guest topology. `host-windows-initial.txt` preserves the first partial interop probe transcoded from GB18030.
- `pmu.log` records the self-thread hardware probe. `pmu-core.log` and the PMU receipts document process-scope collection.
- `sealed-pilot.log` and `receipts/` contain run IDs, validation outcomes and development receipt identities.
- `chronological.jsonl` records real production timings, failed oracles, setup, final-state and RNG hashes, market-work counts, run identities, exact command arguments and raw totals. `pilot-console.log` includes the original failure and the resumed run. `budget.json` is the frozen-schedule planning projection.
- Small logs and receipts from the target are mirrored under `results/acceptance/r4a/archive` in the R4A worktree. The complete raw master is in the target private directory `~/coreorder-r4a-gTl3K1Uz`. The indexed 1,184 files total 2,364,338,311 bytes. Committed text copies normalize line endings and trailing spaces, with Windows streams decoded to UTF-8. The mirror and hashes refer to the original streams. `artifacts.jsonl` lists its relative paths, sizes and SHA-256 digests.

## Reproduce from the recorded R3 source

On the local checkout, create a bundle from the measured ref with `git bundle create r3-source.bundle codex/r3-correctness`. Transfer it to a new private directory on the target. Place the scripts from this directory beside the bundle and use the following commands on Ubuntu x86-64.

```bash
root=/absolute/path/to/new/private-directory
bash "$root/build.sh" "$root"
cd "$root/source"
export PATH="$PWD/.venv/bin:$PATH"
export PYTHONPATH="$PWD:$PWD/build"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
taskset -c 0,2,4,6,8,10,12,14 python -m experiments.run --stage check
taskset -c 0,2,4,6,8,10,12,14 python -m experiments.run --stage pilot \
  --budget-seconds 35 --output "$root/sealed-pilot"
taskset -c 0,2,4,6,8,10,12,14 python "$root/pilot.py" "$root/p01"
PYTHONPATH="$PWD" python "$root/budget.py" "$root/p01/chronological.jsonl" "$root/budget.json"
```

The mask is the measured WSL guest mask for this laptop. Revalidate topology before use elsewhere. The scripts require an unused target directory, the pinned gitlinks, and a clean experiment process tree. P01 uses 11 and 29. Its virtual address space limit is 7 GiB per process. The full W1–W3 validation attempts can consume minutes at this ceiling. Keep failed artifacts.

The PMU frontend is optional. `qualify-perf.sh` extracts existing Ubuntu archive packages under the private experiment root. It leaves the system package database untouched and exercises the published production PMU command with small independent event groups.
