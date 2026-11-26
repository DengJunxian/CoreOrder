#import "style.typ": manuscript, paper-title
#show: manuscript.with(
  "CoreOrder: Deterministic Multicore Execution and Cache-Aware Optimization for Multi-Agent Financial Market Simulation",
  "CoreOrder · Computer Organization",
)

#paper-title(
  [
    CoreOrder: Deterministic Multicore#linebreak()
    Execution and Cache-Aware Optimization#linebreak()
    for Multi-Agent Financial Market Simulation
  ],
  [Parallel team · Computer Organization course paper],
)

#heading(numbering: none, outlined: false)[Abstract]
An optimization of an agent-based market simulator must preserve the sequence of market decisions that determines its workload. CoreOrder studies this constraint in the PAMS financial simulator through two execution changes and one controlled layout comparison. It restores temporarily removed orders by inserting them into the remaining valid heap and executes eligible agent decisions in a native multicore batch while preserving the original Python random streams and submission order. Two layouts expose the same FCN fields to one numeric kernel. On the target x86 host, all 420 C01 correctness runs and 145 V01 runs passed, including 125 candidate receipts against 20 independent V01 reference runs. In a separately instrumented Apple M5 pilot, the W2-H seed-11 comparison count for restoring both sides of the book fell from 8,245,535 to 92,206. A true-input x86 replay calibration showed that the direction of the four-worker comparison changed with prefix size, and AoS had the lower elapsed time at every tested like-for-like calibration point. The formal timing and counter campaign remained unrun. The evidence establishes semantic equivalence for the tested conditions, quantifies the heap's algorithmic work, and identifies which costs must be measured to explain whole-simulator multicore and layout effects.

#text(size: 9.6pt)[*Keywords* · limit order book, deterministic execution, multicore, memory layout, differential validation]

= Introduction

A multi-agent financial market is both a data-processing workload and a feedback system. A decision can insert an order, change an available price, trigger a high-frequency agent, and alter the information available at the next market step. If a faster implementation issues fewer decisions or consumes a different random sequence, its wall time also describes a different market trajectory. A meaningful comparison therefore holds the model, activation sequence, order handling, and random state fixed.

We found two execution boundaries in a pinned PAMS implementation. The matcher temporarily removes candidate orders and then rebuilds each heap, even when the removed set is small. The ordinary-agent collector already defers order submission until collection ends, creating a window in which independent numeric evaluations can execute concurrently. CoreOrder uses those boundaries to implement incremental heap restoration and a deterministic native FCN path. An AoS/SoA comparison within that path exposes the costs of preparing and consuming native inputs.

The contribution is a system adaptation with three separable comparisons: full versus incremental heap restoration, Python versus direct native versus scheduled native execution, and an equal-field layout change. A fourth contribution is an independent, ordered comparison against the unmodified simulator, with receipts that bind correctness to a future measurement condition. The evaluation distinguishes exact same-host validation from instrumented pilots and reports campaign coverage explicitly.

= Related Work

Chiarella and Iori studied an order-driven double auction with heterogeneous traders and a central matching mechanism @chiarella-iori. Hirano, Takata, and Izumi describe PAMS as an extensible Python artificial-market platform @pams-paper. ABIDES illustrates the use of an interactive, message-driven market simulator with configurable latencies @abides. JAX-LOB studies parallel order-book simulation on GPUs for reinforcement-learning workloads @jaxlob. CoreOrder's unit of comparison is one existing CPU market trajectory, with the original workload and random stream held fixed.

Fujimoto's survey frames the need to preserve event causality in parallel discrete-event simulation @fujimoto. Here the stock program supplies a narrower concurrency boundary: pure decision arithmetic after draws have been prepared, followed by original-order consumption. Taskflow supplies a task-graph runtime and scheduling primitives @taskflow-paper. The CoreOrder adapter provides the mapping between row ranges, financial identities, and the serialized order-processing phase.

Amdahl's analysis relates maximum ideal speedup to the serial fraction @amdahl. Roofline connects execution throughput to compute and data movement under a stated model @roofline. Those models motivate separate measurements within the simulator; a timer around a Python/native interface provides neither the arithmetic intensity nor the separable parallel fraction required for quantitative predictions. Kalibera and Jones motivate separating levels of repetition in performance studies @kalibera-jones. The specific pairing and seed-level estimator used here come from the CoreOrder protocol.

= Background and Platform Selection

We selected PAMS because the pinned source exposes a runnable market, an official CI2002 configuration, a sequential reference, and stock thread and process runners @pams-src. The proposal screened alternatives by executable model coverage, license, the size of the semantic adaptation, and laptop feasibility. A reusable complete platform and a collection-before-submission boundary made PAMS appropriate for keeping the financial model fixed while varying CPU execution.

On each order-placement step, the stock sequential runner draws a permutation of ordinary agents. The visit stops when `maxNormalOrders` nonempty agent order lists have been collected or the permutation is exhausted. A list may contain orders for several accessible markets. PAMS then uses its own RNG to permute those lists for handling, retains within-list order, and invokes the stock high-frequency path at its original points. Pricing and tick conversion, matching and expiry, agent cash and positions, market histories, and event hooks remain under the PAMS implementation. The stock Python thread and spawn-process runs serve as distinct comparison points. The stock thread runner also uses a remaining-quota batching principle.

= Research Questions

- *RQ1 · Heap restoration.* How does the ratio of temporarily removed orders to book depth affect restoration work, and where might that work matter to end-to-end time?
- *RQ2 · Native execution.* Can native batches preserve the stock trajectory, and how can the language boundary, scheduling overhead, and worker scaling be measured separately?
- *RQ3 · Layout.* What changes when the same FCN fields and operations use AoS or SoA, accounting for input packing, native view access, and the cache measurement scope?
- *RQ4 · Cost migration.* Which execution intervals become prominent once repeated full-heap restoration is reduced?

= System Architecture

#figure(
  image("../../roles/A/p14/figures/execution-dataflow.pdf", width: 100%, alt: "PAMS execution pipeline from safe batches through packing, native arithmetic, ordered reconstruction, matching, and independent validation."),
  caption: [The production decision path preserves the stock submission stage. Dashed edges indicate the independent reconciliation path used in validation. Adapted from the team's P14 system diagram.],
) <architecture>

== Incremental heap restoration

For one side of the book, let $n$ be the original number of orders, $k$ the number temporarily removed during the pending-execution scan, and $h=n-k$ the remaining size. Each temporary removal is a heap pop, so the remaining array satisfies the heap invariant @cpython-heap. PAMS builds a combined list and heapifies it before executing the pending matches. The resulting restoration work is $O(n)$ per side. CoreOrder pushes the same $k$ order objects into the valid remaining heap. The adjustment requires at most $O(k log(max(n, 2)))$ comparisons, with amortized list growth. These costs describe restoration after the shared scan. A per-call list resize can still move references.

For already inserted orders on one side, the stock comparator establishes a unique priority through order type, side-specific limit price, placement time and order identifier @pams-src. The temporary scan leaves those keys intact. Both strategies produce a valid heap over the same objects. A valid heap therefore exposes the same unique next order, and induction yields the same logical pop sequence. The pending pairs and clearing price have already been determined by PAMS by the time restoration runs. The adapter then invokes the stock execution function in pending-list order. Targeted tests also exercise later book operations that can observe the consequences of restoration.

== Safe decision batches and deterministic consumption

Suppose the collector has $r>0$ remaining nonempty-agent slots. CoreOrder visits the next at most $r$ candidates in the original permutation. Before its last visit, at most $r-1$ candidates in that batch can have contributed a nonempty list, so a sequential collector cannot finish earlier within the same prefix. Empty results leave a residual quota and cause the next prefix to be processed. Multiple orders from one agent still occupy a single slot. This argument relies on the supported FCN decisions observing the same market state during collection.

The main thread takes the original per-agent Gaussian draws in the stock agent and market order. Each accessible market consumes one noise draw and the normal-margin branch consumes a second draw, including the case that ultimately yields an empty order list. Inaccessible markets consume none. CPython stores the cached Gaussian alongside the underlying generator state @cpython-random. CoreOrder passes those sampled values and live market inputs to C++, keeping Python objects and RNGs outside the worker code.

The shared C++17 FCN kernel follows the source operation order. As a mathematical description, let $p$ be the current price, $p_f$ the fundamental, $p_h$ the selected historical price, $h_f,h_c$ the clamped fundamental and effective lookback scales, $z$ the noise draw, and $sigma$ its scale. The signed chart contribution uses $s_c in {-1, 1}$. For weights $w_f,w_c,w_n$ and horizon $H$, the forecast is

$ r_f = (1/h_f) ln(p_f / p), quad
  r_c = (1/h_c) ln(p/p_h), quad r_n = sigma z, $
$ hat(p) = p exp (H dot (1 / (w_f + w_c + w_n))
  dot ((w_f r_f + (w_c r_c) s_c) + w_n r_n)). $

The direction comes from comparing the forecast to the current price. Fixed margin scales the forecast by the direction-specific factor, and normal margin adds the scaled margin draw. The implementation retains the parenthesized evaluation and intermediate double operations, including separate reciprocals. The build disables fast-math and contraction.

The pybind11 adapter validates and keeps the NumPy inputs alive under the GIL, creates an owned output array, releases the GIL around the evaluator, and checks results after return @pybind-src. The direct path evaluates a single range on the calling thread and creates no executor. The parallel path reuses one Taskflow executor per simulation, evaluates disjoint half-open ranges, and waits on the submitted work before using any result @taskflow-src. Slot $i$ always belongs to input row $i$. A range failure is propagated after synchronization, and the production collector rebuilds order lists in their original order on successful completion. Equal inputs and draws yield equal order descriptors within the validated environment. Equal nested order lists then supply equal inputs to stock submission, allowing the same argument to be repeated at the next step.

== Layout and application boundary

Both layout views contain ten 64-bit floating-point fields, three 64-bit integer fields, and two 32-bit integer fields: 112 B of input per row. The common output occupies 16 B. AoS stores fields of one row together, while SoA stores each field in its own dense column. In both cases the scalar kernel consumes the row's market, agent, and sampled numeric fields. Separate metadata binds the row to its agent, market, and call index. Buffer capacity can be reused or enlarged; the active inputs are refreshed each batch so that changing market state and parameters reach the evaluator.

The architecture in @architecture reuses PAMS for the market and Python runner paths, Taskflow for range execution, and pybind11 for the language bridge. CoreOrder owns the restoration adapter, batch integration, strict FCN translation and binding, executor wrapper, layout path, and validation instruments. The evaluated native scope is fee-free markets with exact ordinary `FCNAgent` types and the tested stock market-maker path. Unsupported native inputs are rejected explicitly. A user can select the Python sequential backend before a run.

= Methodology

== Independent correctness and workload checks

The validator runs a separate instance of the pinned PAMS `SequentialRunner` with the same configuration and seed. It compares ordered events, observable per-step state, market history, ledger and logical book contents, and the recorded Python and NumPy RNG state, including the Gaussian cache. Floating-point values are serialized losslessly, and the book is compared in its logical comparator order. The checker also validates financial invariants in the fee-free setting and retains the first structural difference on failure. Independent replay of stock PAMS supplies the expected output.

An eligible condition binds the original input bytes, canonical workload, effective configuration, host, build, dependency identity, actual backend, layout, restore mode, workers, grain, schedule and seed. Comparing the ordered market work covers orders, cancellations, expirations, executions, and market steps; native row counts are a separate observable. An earlier independent validation test shows why both channels matter: intentionally skipping a normal-margin Gaussian draw on an empty result preserves current order events and changes RNG state.

== Timing and inference

Formal `simulation_s` begins at entry to the PAMS simulation and ends once shutdown completes. It includes agent choice, random preparation, packing, native binding and task wait, order construction, order handling and bookkeeping, and PAMS logging. Taskflow construction and start occur during `setup_s`; the lazy Python pools start on first dispatch within simulation time. The parent observes `process_wall_s` across the child lifecycle, including startup, final summaries and output. In timing mode full trajectory snapshots, comparison instrumentation, and profiler hooks are disabled. Profile, replay and PMU attach separate measurement scopes to the same production implementation.

For a complete baseline–variant pair in seed $s$ and block $j$, with times $T_b$ and $T_v$, the protocol specifies

$ d_(s,j) = ln(T_(b,s,j)) - ln(T_(v,s,j)), quad
  m_s = upright("median")_(j in {1,2,3}) d_(s,j), quad
  hat(S) = exp ((1/5) sum_s m_s). $

Pairs share host, workload, seed, repeat and block. Variants follow an assigned order inside each block. The design reports raw observations and median and IQR, and takes the 2.5th and 97.5th percentiles of 10,000 seed-level resamples using bootstrap seed 73021. Native parallel efficiency uses a same-layout and same-restore direct-native baseline and divides speedup by the worker-count ratio. Two warmups per variant are outside the estimator. A timeout is a right-censored driver observation. Any missing required pair makes the aggregate and interval unavailable.

= Experimental Setup

#figure(
  table(
    columns: (1.5fr, 1fr, 1fr, 1fr, 1.45fr),
    table.header[Workload][Agents $N$][Quota $M$][Markets $K$][Steps by session],
    [W0-CI2002 / W0-H], [100], [1], [1], [100 + 500],
    [W1-H], [4,096], [32], [1], [20 + 100],
    [W2-H], [4,096], [256], [1], [8 + 24],
    [W3-LARGE-MULTI], [16,384], [1,024], [4], [2 + 8],
  ),
  caption: [Retained workload shapes. Quota is per session and limits nonempty agent lists per step. W0-H and W0-CI2002 have identical input bytes.],
) <workloads>

The target ASUS host reported an AMD Ryzen AI 7 H 350 with 8 cores and 16 logical threads from Windows. WSL2 reported 32 KiB L1I and 48 KiB L1D per core, 1 MiB L2 per core and 16 MiB shared L3. The Ubuntu 24.04.5 guest used CPython 3.12.3 and the Release C++ extension compiled with GCC 13.3.0, `-O3 -fno-fast-math -ffp-contract=off`. The affinity mask covered guest CPU IDs 0, 2, through 14. The host exposed two Windows efficiency classes; guest affinity provides a virtual CPU constraint. External numeric library threads were limited to one. The native candidate compared 1, 2 and 4 workers with static scheduling at grain 128. Historical P11 diagnostics came from an Apple M5 and use their own measurement boundaries.

The five validation and planned timing seeds were 101, 202, 303, 404, and 505. H01 holds Python serial execution constant and varies heap restoration across the W0/W1/W2 cases in @workloads. E01 uses stock restoration in CI2002 for the existing Python runners and native comparisons. E02 fixes incremental restoration for Python serial, direct native, and Taskflow on W1-H and W3. E03 fixes the formula and execution parameters within each AoS/SoA pair on W2-H and W3. E05 plans separately instrumented profile, PMU, and real-input replay. The evidence supplement records the complete build and protocol identities.

= Evaluation

== Correctness and matched market work

#figure(
  table(
    columns: (1fr, 1.2fr, 1.3fr, 1.2fr, 1.15fr),
    table.header[Suite][Input configs][Reference runs][Candidate runs][Passed],
    [C01], [12], [60], [360], [420 / 420],
    [V01], [4], [20], [125], [145 / 145],
  ),
  caption: [Target x86 correctness on source `58ec5764c218`. Each suite covers five seeds. V01 covers 25 distinct retained conditions. Candidate runs were compared to same-input, same-seed independent PAMS references.],
) <correctness>

@correctness reports the verified correctness census. The matrices include zero quota, empty and sparse access, fixed and normal margins, multiple markets, a fundamental shock, stopped placement and the stock market-maker path. For W3 at seed 101 the direct and 1-, 2-, and 4-worker AoS runs matched the same independent reference, including ordered financial outcomes and complete recorded random state. R4B's receipt checks independently tie the W2-H direct and four-worker AoS/SoA cases to the same model input, effective restoration, and reference. The supporting artifacts identify each cited run.

== Formal performance campaign

The G3 approval lock was blocked at the evidence cutoff. All 435 timing measurements, 58 timing warmups and 76 E05 entries were unrun. Each of the 19 planned performance comparisons lacked all 15 required pairs. Formal end-to-end and isolated effect estimates, confidence intervals, scaling and efficiency are therefore unavailable. The following section reports the observed mechanism and calibration data at their measured scope.

= Performance Mechanism Analysis

== RQ1 · Restoration workload

#figure(
  image("../../roles/A/evidence/P13/figures/heap-mechanism-pilot.pdf", width: 100%, alt: "Pilot restore ratio and comparison counts for both sides of three books, over two seeds."),
  caption: [P11 comparison-instrumented Apple M5 pilot. Six matched workload–seed pairs, two sides per pair. Counts are restoration comparator calls. W0 is the shallow-book comparison.],
) <heap-figure>

The controls in @heap-figure preserve ordered market events, final state, and RNG in each matched pair. At seed 11, W0's buy and sell depths have medians 21 and 22, with median restored fractions of 9.52% and 9.09%. The combined comparisons fall from 14,610 to 3,286. W1-H has depth medians 423 and 307, with counts of 1,710,577 and 38,953 before and after incremental restoration. W2-H has depth medians 925 and 812, with counts of 8,245,535 and 92,206. The median $k$ on both sides is two in all three cases. A shallow book has less scan-and-rebuild work to avoid, while a larger $k/n$ can make rebuilding competitive with reinsertion. These observations quantify changes in comparator work; a crossover and any cache-miss effect require their own measurements.

== RQ2 and RQ3 · Batch size and equal-field replay

#figure(
  image("../../gates/evidence/R5B/artifacts/pilot/replay-calibration.pdf", width: 93%, alt: "Time per row for direct and four-worker AoS and SoA on three captured input prefixes."),
  caption: [Target x86 R4B calibration, W2-H seed 11. Each point represents one launch with 3,000 production binding calls. Elapsed time includes binding, output allocation and executor wait. SoA column preparation precedes the timer.],
) <replay-figure>

The calibration reused 2,048, 4,096 and 8,192 consecutive rows captured from the production W2-H input. The nominal storage of an input prefix plus one output is 256, 512 and 1,024 KiB. All four conditions at each size produced the same output digest. In @replay-figure, four-worker AoS measured 40.06, 27.45 and 20.04 ns per row evaluation; direct AoS measured 30.08, 31.56 and 32.62. Both layouts show the four-worker direction change. These observations are consistent with fixed scheduling costs being amortized as a batch grows. Because every point is a single launch reusing one of three prefixes from the same capture, it gives a descriptive result and little information about machine variation.

AoS elapsed time was lower than SoA in all six equal-executor, equal-prefix calibration comparisons. AoS places inputs for a single FCN evaluation close together. SoA streams the corresponding fields from multiple columns. FCN reads many of the fields and evaluates multiple scalar library functions, so the relative cost can involve stream count, locality, binding overhead, and compute latency. The calibration holds field values fixed but does not observe actual cache residency or isolate each cost. Its nominal footprint omits such allocations as the separate metadata and other runtime objects.

The Apple M5 low-overhead W2-H pilot also preserves two slower direct-native outcomes with the incremental heap fixed. Python and direct elapsed simulation times were 0.213 and 0.272 s for seed 11, and 0.206 and 0.240 s for seed 29. The full pilot includes random preparation, packing and reconstruction. The target x86 PMU pilot established positive userspace cycle, instruction, branch and AMD L1D event counts, with reported 100% coverage in the probes. Counts include the Python worker and inherited tasks. The specific LLC events were unavailable. Formal matched counter data and a decomposition of layout conversion costs are pending.

== RQ4 · Instrumented cost migration

#figure(
  image("../../gates/evidence/R5B/artifacts/pilot/instrumented-spans.pdf", width: 100%, alt: "Pilot cumulative restore and agent decision spans and four subphases of direct native decisions."),
  caption: [Apple M5 P11, W1-H seed 11, three instrumented runs. Each run contributes 1,211 restoration intervals and 120 decision intervals. The direct-native subphases use their own axis. The units are cumulative seconds.],
) <spans-figure>

In @spans-figure the baseline has 11.498 s of measured restoration span and 0.954 s of decision span. Incremental Python has 0.294 s and 0.985 s respectively. Incremental direct-native records 0.276 s of restoration and 1.038 s of decisions. Within the direct decision path, the 120 observations of each subphase accumulate 0.043 s for random preparation, 0.249 s for packing and leasing, 0.00091 s for binding, and 0.038 s for rebuilding orders and releasing the buffer. The reversal between the observed restoration and decision intervals demonstrates migration within this instrumented case. It also shows why timing the native call alone cannot resolve the system comparison. These are inclusive spans, and some stage totals contain other measured spans.

= Discussion

The heap, language boundary, parallel runtime, and data layout act on different units of work. Incremental restore narrows the set involved in restoring heap order. Native migration adds a representation boundary to a small scalar formula. Parallel evaluation can accelerate the numeric segment and also introduces dispatch and completion costs. Layout changes address patterns inside that segment and influences how inputs are prepared. The W0 control and the two negative W2-H pilot observations make the boundaries of isolated optimizations visible.

With serial-baseline fraction $f$ attributable to a truly parallel segment, the ideal Amdahl expression is $1 / ((1-f) + f/w)$ for $w$ workers @amdahl. Its use here requires a same-workload decomposition of that baseline, with a defined boundary between the segment and serial binding, packing, reconstruction, and market work. The present binding and profile intervals provide no identified estimate of $f$. A potential overall gain over stock PAMS also requires a single matched workload measuring both the stock and final combined variants. Separate local comparisons describe separate interventions.

The title's cache-aware scope refers to holding the numeric formula fixed while studying layout, working-set size, and event availability. A layout-dependent replay result can inform a system design without identifying actual cache misses as the cause. A causal interpretation would require matched measurements of the relevant events, a stable CPU measurement scope, and independent accounting for conversion and task execution.

= Threats to Validity

*Internal validity.* Correctness depends on the fixed comparator, supported agent behaviors, numeric operation order and complete RNG handling. The independent oracle checks the tested workload matrix and preserves failures for inspection. Cross-ISA bitwise behavior can vary with compiler and math libraries, and correctness comparisons were made within an environment.

*Measurement validity.* The Apple profile records inclusive intervals under instrumentation. The replay uses repeated warm inputs and includes allocation and native interface costs. Virtual CPU affinity constrains the guest, physical placement across heterogeneous cores and sustained frequencies are only partly observable, and the target lacks the selected LLC events. These limits bound any cache or throughput inference drawn from the pilots.

*Statistical and external validity.* The formal sample unit is the seed, and five seeds would yield a coarse empirical distribution even after three technical repeats. The present formal data set contains zero observations. The evaluated application scope is the pinned fee-free PAMS workloads and supported strategies. Results concern simulator execution and provide no evidence about predictive validity in an actual exchange.

= Conclusion

CoreOrder localizes three CPU research interventions in a complete financial simulator and holds the original market trajectory as their common comparison point. Independent target-host validation confirms the tested heap, backend and layout paths against stock PAMS. The measured comparison counts explain why restoring a small set in a deep heap can eliminate substantial work. Replay and profiling expose the size dependence of native scheduling and the importance of the data boundary. Together these results establish a reproducible architecture and a bounded mechanism account. Formal system speedups, layout effects and counter comparisons remain pending under G3.

#heading(numbering: none)[Contributions and Artifact Availability]
A established the platform and shared contracts, adapted heap restoration and safe batching, and integrated the production paths and later measurement pipeline. B implemented the FCN numeric kernel and binding. C implemented the Taskflow executor wrapper, range discipline and synchronization. D implemented the AoS/SoA representation, live packing and buffers. E built the independent reference, fault tests and record methods that anchor validation and the experimental design. The supplement traces each role to source commits and each evaluation result to source data. The project and original member branches are available in the #link("https://github.com/DengJunxian/CoreOrder")[CoreOrder repository]. The manuscript and the R5B evidence package are identified in the supplement.

#bibliography("references.bib", style: "ieee", title: [References])
