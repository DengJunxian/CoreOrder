# CoreOrder R8 · public review handoff

This branch is the public review mirror of local R8, prepared for reading the code, assessing the evidence, and planning future work. Begin with the [FINAL audit](gates/FINAL.md), [R8 version ledger](gates/evidence/R8/versions.json), and [course paper and reproducibility guide](paper/R6/README.md).

| Start here | What it contains |
| --- | --- |
| [README](../README.md), [contract](CONTRACT.md), [experiment guide](EXPERIMENTS.md) | Pinned dependencies, build and run instructions, backend/data contracts, tests, and measurement scopes. |
| [G0](gates/G0.md), [G1 heap](gates/G1-heap.md), [G1 native](gates/G1-native.md), [G2](gates/G2.md), [G3](gates/G3.md) | Technical evidence and outstanding team approvals. Historical subsections describe older configurations. |
| [R4B protocol](../configs/experiments/r4b/frozen.json), [C01 index](gates/evidence/R4B/c01-index.json), [V01 index](gates/evidence/R4B/v01-index.json) | Reviewed schedule and public validation indexes. C01 was 420/420 and V01 was 145/145 on ASUS x86. |
| [R5B report](gates/R5B.md), [coverage CSV](gates/evidence/R5B/artifacts/formal-pairing-coverage.csv), [figure provenance](gates/evidence/R5B/README.md) | Diagnostic evidence, preliminary figures and missing formal comparisons. |
| [Paper claims](paper/R6/claim-evidence.csv), [roles A–E](gates/evidence/R8/CONTRIBUTIONS.md), [publication review](gates/evidence/R8/RELEASE.md) | Claim-to-evidence mapping, original implementation and integration provenance, and the remaining release work. |

The engineering snapshot matches tested source `58ec5764c21833142c50abacd9e2302404ffdb06` for production, build and verification paths. The local R8 document commit is `3ed7f4387e87e695ccbaed46dbdd50bd59fc6ef7`. Public text records use path placeholders such as `<MAC_HOME>` and `<LINUX_HOME>`. The corresponding distributed file checksum lists describe the public copies. Digests and statements of identity in historical run records still describe the original evidence. A redacted protocol lock has a different file digest and candidate identifier from the private R4B original. Original sealed raw and the large x86 archive are kept in the project team's restricted evidence storage.

## Outstanding work

1. Obtain hosted CI and independent signoffs against the exact version that will be tested. Use the sealed V01 results to review an effective G3 lock before launching formal measurements.
2. Collect the approved timing and E05 campaigns under that lock. The current formal count is zero. All 569 planned entries are unrun, including 70 warmups. The 19 formal paired estimates are missing. The pilot and calibration figures have their own measurement scopes.
3. Obtain and archive a non-author reproduction receipt, the combined team slides, and a rehearsal record. The repository contains the existing member A deck and the available team evidence.
4. Audit the release candidate and any visible Git history before merging or publishing a stable release.

`FINAL` and `G3` remain BLOCKED. This branch supports review and planning.
