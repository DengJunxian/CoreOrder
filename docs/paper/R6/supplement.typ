#import "style.typ": manuscript, paper-title
#show: manuscript.with("CoreOrder · Supplementary Evidence", "CoreOrder · Supplementary Evidence")

#paper-title([CoreOrder: Supplementary Evidence], [Parallel team · Evidence cutoff 26 November 2026])

= Versioned experiment artifacts

The target correctness build uses CoreOrder commit `58ec5764c21833142c50abacd9e2302404ffdb06`, x86 host ID `7fd1261e162f2fef` and an independently identified loaded extension. The R4B candidate and R5B evidence revisions identify the protocol and records.

#table(
  columns: (1.1fr, 3fr),
  table.header[Artifact][Identity],
  [Candidate protocol], [`8113c98d7c108b8fd33dd86d35c7c63e890cf6f05fd731ded36551c26ce0219c`],
  [x86 native SHA-256], [`a9d294e6bac9098bb486d1ba3e728a0fa9f974eb858ad107fde858b86e16fc5e`],
  [x86 environment SHA-256], [`66efa4e180a9c83500d1ebc9ced921938d0651913c811dd07e2e9084f197d163`],
  [R5B evidence snapshot], [`a58c37842b0bc3583410bbf24f8eb7ca9fb29877`],
  [Historical P11 pilot], [`3c344f765c6ff288abad2faa6081c921f0ee0f36`],
)

Each verified receipt binds the source, three upstreams, environment, pristine input and canonical form, effective configuration, actual backend, restore policy, workers, layout, grain, schedule and seed, plus both run IDs and hashes of the ordered comparison, trace and invariant artifacts. Formal data collection additionally requires the approved G3 lock. The G0 foundation, G1 heap and native, and G2 integrated correctness have technical evidence. The associated same-version formal approvals remain blocked, and the G3 execution lock remains inactive.

#table(
  columns: (1fr, 1.65fr, 1.15fr, 2.2fr),
  table.header[Upstream][Pinned commit][License][Used for],
  [PAMS 0.3.0], [`6cd53810103780770` `c5b5d6ee0069ccab` `9f4b358`], [EPL-1.0], [Stock financial machinery and runners, as well as the FCN expression underlying the numeric adaptation],
  [Taskflow 3.11.0], [`816b4ad53b44196c` `88f409eb7b4a25a0` `e3bfdf42`], [MIT], [Task graph, worker pool and partitioners],
  [pybind11 2.13.6], [`a2e59f0e7065404b` `44dfe92a28aca47b` `a1378dc4`], [BSD-3-Clause], [Bindings, dtype and buffer conventions, GIL boundary],
)

Commit fragments in each row concatenate in reading order. Full identifiers, immutable upstream links, and license copies are in the source audit. The pinned PAMS project version identifies this code snapshot.

#pagebreak(weak: true)

= Correctness and replay anchors

#table(
  columns: (1.55fr, 1.25fr, 2.5fr),
  table.header[Workload and seed][Condition][Recorded run ID],
  [W1-H · 101], [Stock restore], [`4d4084b6033b4b5eb8ca82c3742dd275`],
  [W1-H · 101], [Incremental], [`19fe7d05557c4fe0be3b162500a9c2d8`],
  [W3 · 101], [Independent PAMS], [`07e25c0ca8ff4ed495db1e8f2d9639b5`],
  [W3 · 101], [Python incremental], [`5d586ed82d0d4977a083ebfc71ff9a22`],
  [W3 · 101], [AoS direct], [`640b5f6c9bba4f7aa15d364d08e7e394`],
  [W3 · 101], [AoS pool / 1], [`de8bffca9d094f57a408de772e5a245b`],
  [W3 · 101], [AoS pool / 2], [`2634ac654d9f4985881fe920cd137027`],
  [W3 · 101], [AoS pool / 4], [`43e87f1199734fe7bc60b680a37988bd`],
  [W2-H · 101], [AoS direct], [`6d10cadf6ca44b87b8e40221f4e24bea`],
  [W2-H · 101], [SoA direct], [`9dd51cbeb0ed47a7a1a58c4bf04f8446`],
  [W2-H · 101], [AoS pool / 4], [`a172bdfc58f3408db6a20f8adbdd0625`],
  [W2-H · 101], [SoA pool / 4], [`19cbce45be344a11a24d0c8d5dc86e80`],
)

These anchors locate complete production/reference records in the V01 index. The x86 calibration in the paper used a different capture, W2-H seed 11, with source run ID `f86a22b159ee40e09cb1a4e461b8aaa0`. Its twelve replay measurements and exact command and byte hashes are indexed in R5B. The reserved E05 seed-101 input is associated with the W2-H direct AoS validation record above.

= Formal experiment coverage

#table(
  columns: (1fr, 1fr, 1fr, 1fr, 1fr, 1fr, 1.2fr),
  table.header[Phase][Planned][Warmup][Valid][Failed][Timeout][Unrun],
  [H01], [102], [12], [0], [0], [0], [102],
  [E01], [85], [10], [0], [0], [0], [85],
  [E02], [170], [20], [0], [0], [0], [170],
  [E03], [136], [16], [0], [0], [0], [136],
  [E05], [76], [12], [0], [0], [0], [76],
  [Total], [569], [70], [0], [0], [0], [569],
)

The E05 plan has 4 profile, 24 PMU and 48 replay entries. The 12 diagnostic warmups are within replay. The R5B paired-coverage table lists 19 planned comparisons, each requiring 15 valid pairs over five seeds. Across comparisons there are 285 empty pair positions, including shared baselines. Every aggregate is unavailable. The final evidence inventory contains candidate validation and pilot attempts with their original scopes.

#pagebreak(weak: true)

= Interpretation of instrumentation

#figure(
  image("../../roles/A/p14/figures/heap-restore.pdf", width: 90%, alt: "Drawing of stock heapify and incremental pushes starting from the remaining heap."),
  caption: [Schematic of the heap operation boundary. Pending pairs and clearing price are fixed by the stock scan. The drawing has no measured values.],
) <heap-schematic>

P11 saved all comparator-instrumented runs, with separate ordered-workload verification. Two baseline W2-H comparator attempts hit the pilot limit, and their completed retries have distinct case paths. The P13 index ties the plotted counts to those completed diagnostic cases and preserves the censored attempts. The R5B stage figure ties each instrumented interval to the original phases file hash. The replay chart normalizes binding elapsed time by rows times 3,000 calls.

The WSL2 preflight used userspace counting. In the production pilot the tested groups aggregate the Python worker and inherited tasks, including startup, simulation and summaries. Multiplex running coverage was reported as 100% for the supported groups under these tests.

#table(
  columns: (1.4fr, 1.0fr, 2.6fr),
  table.header[Event group][R4A status][Interpretation],
  [Cycles / instructions], [Available], [Userspace cycles and retired instructions. Case-level IPC requires compatible observations from the same scope.],
  [Branches / misses], [Available], [Retired branches and mispredicted retired branches on the target mapping.],
  [L1D pair], [Available], [Data Cache accesses and L1D misses that request L2 access on the target mapping. The two events require their own denominators.],
  [Dedicated LLC pair], [Unavailable], [Direct probe returned ENOENT. The production tool reported unsupported on the tested platform.],
)

The supported groups were qualification probes. The E05 campaign defines the matched measurements needed to compare layouts or backends. All E05 hardware differences remain unavailable.

#pagebreak(weak: true)

= Contribution provenance

#table(
  columns: (.55fr, 2.95fr, 1.5fr),
  table.header[Role][Original contribution][Commit anchors],
  [A], [Pinned platform, contracts, heap adapter, safe batch adaptation and production integration. A carried out later timing, reporting and x86 streaming-checkpoint integration.], [`614dacf`, `da29dd6`, `92f8bbf`, `c3a0c52`, `dee54bb`, `58ec576`],
  [B], [Production FCN numeric expression, common direct/range kernel, binding, strict value and error tests.], [`0e5bf62`],
  [C], [Persistent Taskflow wrapper, exclusive ranges, synchronized completion, deterministic error behavior and module regressions.], [`e615358`, `cfe9877`],
  [D], [Two equal-field data layouts, buffer leases, production packing and live event refresh tests.], [`a56e485`, `3ef2298`],
  [E], [Independent PAMS reference, ordered collector, fault tests, reproducible first differences, record contracts and evaluation method. Production timing and reporting integration by A uses these contracts.], [`533ab87`],
)

= Source data and figure reproduction

The manuscript source is `docs/paper/R6/main.typ`. The neighboring reference audit and claim ledger list the supporting files, running identities and verified publications. R4B's `c01-index.json` and `v01-index.json` provide case paths and seals on the target host. R5B's evidence README lists each original figure PDF, CSV, renderer and archived raw index. The repository checkout has the audit mirrors and sealed indexes; large target validation traces and historical local pilot files are identified by their archived locations and hashes.

The R5B generator reproduces the validated correctness and hardware tables as well as the two pilot figures. P13's generator reproduces the comparator-work figure. The P14 Graphviz source supplies the two explanatory diagrams. The scope of the fifteen-pair statistical pipeline is recorded in the candidate runlist and the formal coverage CSV. Authorized timing and diagnostics can enter `analysis.report` after their sealed evidence is available.
