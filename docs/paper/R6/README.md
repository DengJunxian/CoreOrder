# CoreOrder R6 · Course paper candidate

[Paper PDF](CoreOrder.pdf) · [Editable paper](main.typ) · [Supplement PDF](CoreOrder-Supplement.pdf) · [Editable supplement](supplement.typ) · [BibTeX](references.bib) · [Reference and reuse audit](REFERENCE_AUDIT.md) · [Claim–evidence ledger](claim-evidence.csv)

The main document is an English, single-column academic course paper under the requested title. The R4 proposal identifies the course as Computer Organization and the group as Parallel. The provided materials use A–E role labels and supply no final page limit, required template, or approved author-name roster. The current typesetting uses A4, numbered sections, and numeric references. The title's cache-aware scope is the equal-field layout, capture and measurement design.

The correctness results come from complete x86 C01/V01 runs on `58ec5764c21833142c50abacd9e2302404ffdb06`. Pilot work, replay and stage observations carry explicit captions and source IDs. The R5B cutoff has zero formal timing/diagnostic observations and 19 unavailable paired estimates. The existing G3 approval status is preserved. [R5B report](../../gates/R5B.md) · [G3 evidence](../../gates/G3.md) · [19 planned comparisons](../../gates/evidence/R5B/artifacts/formal-pairing-coverage.csv)

## Figure and table sources

| Paper output | Source and scope |
| --- | --- |
| Figure 1, execution and validation architecture | [P14 vector source](../../roles/A/p14/figures/execution-dataflow.pdf) · [Graphviz](../../roles/A/p14/figures/execution-dataflow.dot) |
| Tables 1–2, x86 workloads and correctness | [Workloads](../../gates/evidence/R5B/artifacts/validation/workloads.csv) · [Correctness CSV](../../gates/evidence/R5B/artifacts/validation/correctness.csv) · [Standalone correctness PDF](../../gates/evidence/R5B/artifacts/validation/correctness.pdf) |
| Figure 2, heap restoration comparison counts | [P13 vector output](../../roles/A/evidence/P13/figures/heap-mechanism-pilot.pdf) · [Plotted data](../../roles/A/evidence/P13/figures/heap-mechanism-pilot.csv) · [Original archive and renderer](../../roles/A/evidence/P13/INDEX.md) |
| Figure 3, true-input replay calibration | [R5B vector output](../../gates/evidence/R5B/artifacts/pilot/replay-calibration.pdf) · [CSV](../../gates/evidence/R5B/artifacts/pilot/replay-calibration.csv) · [Raw capture and run index](../../gates/evidence/R5B/replay-raw-index.json) |
| Figure 4, P11 instrumented phase spans | [R5B vector output](../../gates/evidence/R5B/artifacts/pilot/instrumented-spans.pdf) · [CSV](../../gates/evidence/R5B/artifacts/pilot/instrumented-spans.csv) · [Original phase file index](../../gates/evidence/R5B/p11-phase-raw-index.json) |
| Supplementary schematic and hardware table | [P14 heap schematic](../../roles/A/p14/figures/heap-restore.pdf) · [Graphviz](../../roles/A/p14/figures/heap-restore.dot) · [R5B hardware and configuration PDF](../../gates/evidence/R5B/artifacts/validation/configuration.pdf) |
| Formal H01/E01/E02/E03 plots and E05 figures | NOT_RUN. [Formal phase coverage](../../gates/evidence/R5A/formal-coverage.json) · [R5B target inventory and report rejection](../../gates/evidence/R5B/x86-inventory.log) |

The [R5B reproducibility index](../../gates/evidence/R5B/README.md) describes the original data, generator commands and claim scope, including separation of embedded vector diagnostics from formal results. C01/V01 sealed raw traces are on the recorded target host. The repository maintains the [C01 index](../../gates/evidence/R4B/c01-index.json), [V01 index](../../gates/evidence/R4B/v01-index.json), and diagnostic mirrors.

## Build and verify

From the repository root with Typst 0.15.1:

```sh
typst compile --root . --creation-timestamp 1795622400 docs/paper/R6/main.typ docs/paper/R6/CoreOrder.pdf
typst compile --root . --creation-timestamp 1795622400 docs/paper/R6/supplement.typ docs/paper/R6/CoreOrder-Supplement.pdf
(cd docs/paper/R6 && shasum -a 256 -c SHA256SUMS)
```

The two source files read the versioned vector figures through repository-relative paths. They use Libertinus Serif, New Computer Modern Math and Helvetica when available, with a New Computer Modern heading fallback. The check in [QA.md](QA.md) records the actual build, numerical cross-checks, citation and figure checks, and layout inspection. Raw experimental evidence and the candidate protocol are retained in their original locations.
