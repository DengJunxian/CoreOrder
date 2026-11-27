"""Draw only source-qualified study figures and retain their raw-data lineage."""

from collections import Counter, defaultdict
from math import exp

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt

from experiments.protocol import file_hash
from validation.io import write

COLORS = ("#174860", "#a8422b", "#567455", "#785687", "#72777b")
PHASE_NAMES = {
    "draw_pack_s": "Draw + pack",
    "native_compute_s": "Native binding + wait",
    "rebuild_orders_s": "Rebuild orders",
    "handle_orders_s": "Handle orders",
    "optional_restore_s": "Heap restoration",
}


def source_rows(comparisons, rows):
    ids = {side["run_id"] for item in comparisons for block in item["blocks"]
           for side in (block["reference"], block["variant"]) if side.get("run_id")}
    return [row for row in rows if row.get("run_id") in ids]


def render_figures(report, specification, directory):
    results = directory / "figures"
    results.mkdir()
    rows = report["rows"] + report["additional_sources"]
    scope = report["scope"]
    developmental = scope in ("candidate-validation", "development-pilot")
    label = "Development evidence" if developmental else "CoreOrder R4"
    artifacts = {}
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
        "axes.axisbelow": True, "pdf.fonttype": 42, "svg.hashsalt": "coreorder-r4",
    })

    def draw(name, title, source, plot, size=(6.4, 3.5)):
        if not source:
            artifacts[name] = {"status": "NOT_RUN"}
            return
        fig, axis = plt.subplots(figsize=size, layout="constrained")
        try:
            plot(axis, source)
            axis.set_title(f"{title}\n{label}", loc="left", fontsize=11)
            fig.savefig(results / f"{name}.pdf", metadata={"CreationDate": None, "ModDate": None})
            fig.savefig(results / f"{name}.png", dpi=190)
        finally:
            plt.close(fig)
        artifacts[name] = {"status": "PASS", "scope": scope, "source": [
            {key: row.get(key) for key in ("case_id", "run_id", "status", "record_sha256", "raw_directory")}
            for row in source
        ], "output_sha256": {ext: file_hash(results / f"{name}.{ext}") for ext in ("pdf", "png")}}

    def correctness(axis, source):
        by_phase = defaultdict(Counter)
        for row in source:
            phase = "Pilot" if row["phase"] == "P01" else row["phase"]
            by_phase[phase][row["status"]] += 1
        offsets = [0] * len(by_phase)
        for status, color in zip(("PASS", "FAIL", "TIMEOUT", "UNSUPPORTED", "NOT_RUN"), COLORS):
            counts = [values[status] for values in by_phase.values()]
            if any(counts):
                axis.barh(list(by_phase), counts, left=offsets, color=color, label=status, height=0.5)
                offsets = [left + count for left, count in zip(offsets, counts)]
        axis.set_xlabel("Planned verification runs")
        axis.legend(frameon=False)

    def comparisons(name, title, data, curve=False, efficiency=False):
        metric = "parallel_efficiency" if efficiency else "speedup"
        ci = "efficiency_ci95" if efficiency else "speedup_ci95"
        complete = [item for item in data if item[metric] is not None]
        plotted = source_rows(complete, rows)

        def plot(axis, _):
            if curve:
                by_workload = defaultdict(list)
                for item in complete:
                    by_workload[item["workload"]].append(item)
                for color, (workload, items) in zip(COLORS, by_workload.items()):
                    items.sort(key=lambda item: item["workers"])
                    workers, values = [[item[key] for item in items] for key in ("workers", metric)]
                    bounds = [item[ci] for item in items]
                    axis.plot(workers, values, "o-", color=color, label=workload)
                    axis.vlines(workers, [b[0] for b in bounds], [b[1] for b in bounds], color=color, alpha=0.8)
                axis.set_xticks(sorted({item["workers"] for item in complete}))
                axis.set_xlabel("Taskflow workers")
                axis.set_ylabel("Parallel efficiency" if efficiency else "Paired speedup")
                axis.axhline(1, color="#717780", linestyle="--", linewidth=0.8)
                axis.legend(frameon=False)
                axis.grid(axis="y", alpha=0.22)
                return
            labels = [f"{item['workload']}  |  {item['reference']} → {item['variant']}" for item in complete]
            for index, item in enumerate(complete):
                effects = [exp(row["median_log_ratio"]) for row in item["seed_effects"].values()]
                axis.scatter(effects, [index] * len(effects), facecolors="none", edgecolors=COLORS[0],
                             alpha=0.55, s=27, zorder=2)
                axis.hlines(index, *item[ci], color=COLORS[1], linewidth=2, zorder=3)
                axis.scatter(item[metric], index, marker="D", color=COLORS[1], s=27, zorder=4)
            axis.set_yticks(range(len(labels)), labels)
            axis.invert_yaxis()
            axis.axvline(1, color="#717780", linestyle="--", linewidth=0.8)
            axis.set_xlabel("Paired speedup (reference / variant)")
            axis.grid(axis="x", alpha=0.22)
        draw(name, title, plotted, plot, (7.0, max(2.8, 1.5 + 0.33 * len(complete))))

    def phase_plot(keys):
        def plot(axis, source):
            count = len(source)
            width = 0.72 / count
            for index, row in enumerate(source):
                present = [(pos, row["phases_ms"][key]) for pos, key in enumerate(keys)
                           if row["phases_ms"][key] is not None]
                positions = [pos + (index - (count - 1) / 2) * width for pos, _ in present]
                name = row.get("variant") or f"{row['workload']} · {row['backend']} · {row['book_restore']}"
                axis.bar(positions, [value for _, value in present], width, color=COLORS[index % len(COLORS)], label=name)
            axis.set_xticks(range(len(keys)), [PHASE_NAMES[key] for key in keys], rotation=13, ha="right")
            axis.set_ylabel("Instrumented time (ms)")
            axis.legend(frameon=False, fontsize=8)
            axis.grid(axis="y", alpha=0.20)
        return plot

    def replay(axis, source):
        series = defaultdict(lambda: defaultdict(list))
        for row in source:
            data = row["replay"]
            series[(data["layout"], data["backend"], data["workers"])][data["rows"]].append(
                data["replay_s"] * 1e9 / data["replay_row_evaluations"],
            )
        for color, (label, values) in zip(COLORS, series.items()):
            sizes = sorted(values)
            for size in sizes:
                axis.scatter([size * 112 / 1024] * len(values[size]), values[size], color=color, alpha=0.35)
            from statistics import median
            axis.plot([size * 112 / 1024 for size in sizes], [median(values[size]) for size in sizes],
                      "o-", color=color, label=f"{label[0].upper()} · {label[1]} · {label[2]} workers")
        axis.set_xscale("log", base=2)
        axis.set_xlabel("FCN input size (KiB)")
        axis.set_ylabel("Binding replay time (ns / evaluated row)")
        axis.legend(frameon=False, fontsize=8)
        axis.grid(axis="y", alpha=0.20)

    def pmu(axis, source):
        categories = defaultdict(list)
        for row in source:
            for counter in row["pmu"]["rows"]:
                categories[(counter["event"], counter["unit"])].append(
                    (f"{row['layout']} · {row['workload']}", counter["count"]),
                )
        # One output per event and unit preserves scale and scope.
        entries = next(iter(categories.values()))
        labels = list(dict.fromkeys(name for name, _ in entries))
        for index, label in enumerate(labels):
            axis.scatter([count for name, count in entries if name == label], [index] * sum(
                name == label for name, _ in entries), color=COLORS[index % len(COLORS)])
        axis.set_yticks(range(len(labels)), labels)
        event, unit = next(iter(categories.keys()))
        axis.set_xlabel(f"{event} ({unit or 'raw count'}, full process)")
        axis.grid(axis="x", alpha=0.20)

    prefix = "pilot-" if developmental else ""
    requested = {item["id"]: set(item["source"]) for item in specification}
    correct = [row for row in rows if row["mode"] == "validation" and
               (developmental or row["phase"] in requested["F1"])]
    draw(prefix + "F1-correctness", "Independent validation outcomes", correct, correctness)
    profiles = [row for row in rows if "phases_ms" in row]
    draw(prefix + "F2-bottlenecks", "Matching and restoration · inclusive spans", profiles,
         phase_plot(("handle_orders_s", "optional_restore_s")))
    native_phases = [row for row in profiles if row["phases_ms"]["native_compute_s"] is not None]
    draw(prefix + "F6-production-phases", "Preparation, native binding and rebuild", native_phases,
         phase_plot(("draw_pack_s", "native_compute_s", "rebuild_orders_s")))
    data = report["comparisons"]
    comparisons(prefix + "F2-heap", "Heap restoration speedup", [item for item in data if item["phase"] == "H01"])
    comparisons(prefix + "F3-native", "Native and baseline contrasts",
                [item for item in data if item["phase"] in requested["F3"] | {"P01"}])
    scale = [item for item in data if item["phase"] in requested["F4"] | {"P01"} and
             item["parallel_efficiency"] is not None]
    comparisons(prefix + "F4-workers", "Native scaling", scale, curve=True)
    comparisons(prefix + "F4-efficiency", "Native parallel efficiency", scale, curve=True, efficiency=True)
    comparisons(prefix + "F5-layout", "AoS / SoA end-to-end comparison",
                [item for item in data if item["phase"] == "E03"])
    draw(prefix + "F6-workset", "Captured FCN input size and replay cost",
         [row for row in rows if "replay" in row and not row["warmup"]], replay)
    counters = defaultdict(list)
    for row in rows:
        if row.get("pmu_quality", {}).get("status") != "QUALIFIED" or "pmu" not in row:
            continue
        for counter in row["pmu"]["rows"]:
            if counter["count"] is not None:
                counters[(counter["event"], counter["unit"])].append((row, counter))
    for index, (_, selected) in enumerate(sorted(counters.items()), 1):
        displayed = [{**row, "pmu": {**row["pmu"], "rows": [counter]}} for row, counter in selected]
        draw(prefix + f"F5-pmu-{index}", "PMU evidence · recorded events", displayed, pmu)
    if not counters:
        pmu_rows = [row for row in rows if row["mode"] == "pmu"]
        status = "MISSING" if any(row.get("pmu_quality") for row in pmu_rows) else "NOT_RUN"
        artifacts[prefix + "F5-pmu"] = {"status": status}
    artifacts["T7"] = {"status": "NOT_RUN", "reason": "separate qualified platform evidence not supplied"}
    index = {"scope": scope, "report_sha256": file_hash(directory / "report.json"),
             "matplotlib_version": matplotlib.__version__, "figures": artifacts}
    write(results / "lineage.json", index)
