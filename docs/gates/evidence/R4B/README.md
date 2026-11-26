# R4B evidence and reproducibility

The target runs used the clean source commit `58ec5764c21833142c50abacd9e2302404ffdb06`. Its target binary and environment are recorded in `candidate-identity.json`. The raw master is under `~/coreorder-r4b-sPvokUVq` on the ASUS research host. The documentation and protocol checkout can advance independently of the source and binary recorded by the runner.

## Validation representation

The formal preflight runs select `--stream-validation`, and the independent PAMS CLI selects `--stream`. The file convention remains `oracle-trace.json.gz` and `validation-trace.json.gz`. This avoids changing receipt file slots. The first frame identifies the format. The rest are ordered channel/tag, tab, canonical JSON, LF records. They contain initial state, all E events, every checkpoint, and final state. Exact canonical bytes are matched under the same observation contract. The existing conservation and event-ledger-book checks iterate the stream.

The `mt_words` lists define implicit consecutive IDs for exact little-endian arrays of 624 unsigned 32-bit MT19937 words. A reference contains Python state version, word-array ID, current word index, and exact Gaussian-cache hex value or null. The first appearance of an equal binary array defines its ID. Every defined word is present for byte-level comparison, and every per-checkpoint reference, index and normal cache is recorded. NumPy generator state stays in the original explicit encoding. The test fixture reconstructs the original E structures from all frames and verifies that a single-word corruption causes rejection.

On the same source, the receipt gate and CoreOrder CLI both check the same independent data, and the raw seal includes the trace, invariants, and differential artifacts. A streaming failure leaves the exact full input, first differing location, and the two source artifacts available for review.

## Target build and execution

Prepare a fresh private directory on the existing target. Transfer a Git bundle with the exact source SHA and the scripts here. Use the verified R4A cache only as the source of the three pinned upstream repositories. The CMake Release build is a fresh build.

```bash
root=/absolute/path/to/private-directory
sha=58ec5764c21833142c50abacd9e2302404ffdb06
bash "$root/build-x86.sh" "$root" "$sha"
cd "$root/source"
export PATH="$PWD/.venv/bin:$PATH" PYTHONPATH="$PWD:$PWD/build"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
mask=0,2,4,6,8,10,12,14
taskset -c "$mask" python "$root/calibrate-x86.py" "$root/rehearsal" "$sha"
(ulimit -v 7340032; taskset -c "$mask" python -m experiments.run --stage C01 --budget-seconds 2400 --output "$root/C01")
(ulimit -v 7340032; taskset -c "$mask" python -m experiments.run --plan "$root/approved" --stage V01 --budget-seconds 4800 --output "$root/V01")
```

Regenerate the exact pre-V01 plan using `revise_candidate.py`, the original P12 files, the observed runtime/environment and the x86 compilation database. The approved W2-H reuse is enabled by `--reuse-w2-h`. Its planned seeds, stage limits and eligibility are checked by `experiments.run --stage check`. Do not use edited candidate files to resume an existing batch. The C01 command used the original immutable plan with the same C01 schedule. The revised validation plan and reviewed execution candidate can have separate file hashes. Compare cases and runtime identities when linking their evidence.

`audit_batch.py` reopens raw seals and checks every accepted receipt plus its exact upstream reference. `replay_capture.py` wraps the production bound evaluator for observation and preserves its actual result. Formal replay-source capture requires a sealed V01 receipt for that precise real config and seed, and checks the resulting economy and RNG digests. A rehearsed common repeat count uses pilot seed 11, independently of any formal timing data.

The full batch evidence is indexed in `c01-index.json` and `v01-index.json`. The reviewed candidate is in [configs/experiments/r4b](../../../../configs/experiments/r4b/). It is a complete evidence-linked candidate, with formal execution blocked by outstanding same-version team reviews. A future eligible launch would pair an authorized plan directory with the recorded target source and exact extension. The sealed V01 directory is retained separately as the qualification input.

For future PMU runs, the recorded userspace perf is under `~/coreorder-r4a-gTl3K1Uz/perf-tools`. Its `bin` directory belongs at the front of PATH and its extracted `usr/lib/x86_64-linux-gnu` directory is needed on LD_LIBRARY_PATH. Verify its SHA-256 against `pmu-tool-identity.log` during launch preflight.
