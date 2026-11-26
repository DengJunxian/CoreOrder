"""Regenerate the P11 mechanism figure and its backing table."""

import csv
import hashlib
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter


OUTPUT = Path(__file__).resolve().parent
WORKLOADS = ("W0-CI2002", "W1-H", "W2-H")
SEEDS = (11, 29)
SIDES = ("buy", "sell")
MODES = ("upstream", "incremental")
GEOMETRY = ("restore_calls", "sum_n", "sum_h", "sum_k", "n_p50", "k_p50",
            "ratio_p50", "ratio_p99", "ratio_max")
PAIRS = [(workload, seed) for workload in WORKLOADS for seed in SEEDS]
POSITIONS = (0, 1, 2.5, 3.5, 5, 6)
TICKS = tuple(f"{workload[:2]}\n{seed}" for workload, seed in PAIRS)
UPSTREAM = "#31536D"
INCREMENTAL = "#007A68"


def read_pairs(source):
    with source.open(newline="") as file:
        records = list(csv.DictReader(file))
    indexed = {(r["workload"], int(r["seed"]), r["side"], r["restore"]): r for r in records}
    assert len(records) == len(indexed) == len(PAIRS) * len(SIDES) * len(MODES)
    rows = []
    for workload, seed in PAIRS:
        for side in SIDES:
            upstream, incremental = (indexed[workload, seed, side, mode] for mode in MODES)
            assert upstream["backend"] == incremental["backend"] == "py-seq"
            assert upstream["status"] == incremental["status"] == "PASS"
            assert upstream["purpose"] == incremental["purpose"] == "heap"
            assert all(upstream[field] == incremental[field] for field in GEOMETRY)
            assert int(upstream["sum_n"]) == int(upstream["sum_h"]) + int(upstream["sum_k"])
            rows.append({
                "scope": "P11 pilot", "workload": workload, "seed": seed, "side": side,
                **{field: upstream[field] for field in GEOMETRY},
                "upstream_comparisons": upstream["comparison_calls"],
                "incremental_comparisons": incremental["comparison_calls"],
                "upstream_case": upstream["case"], "incremental_case": incremental["case"],
            })
    return rows


def render(rows):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.4,
                         "pdf.fonttype": 42, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.labelcolor": "#233344",
                         "axes.titleweight": "bold", "axes.titlesize": 10,
                         "legend.fontsize": 8.1, "legend.frameon": False})
    fig, (fraction, comparisons) = plt.subplots(1, 2, figsize=(7.8, 3.85))
    fig.subplots_adjust(left=0.107, right=0.973, bottom=0.277, top=0.756, wspace=0.34)
    fig.text(0.107, 0.94, "Heap restoration in the P11 pilot", fontsize=14,
             weight="bold", color="#152635")
    fig.text(0.107, 0.874, "Both modes processed the same ordered buy- and sell-side restore records.",
             color="#43576A")

    for pair, pos in zip(PAIRS, POSITIONS, strict=True):
        buy, sell = [r for r in rows if (r["workload"], r["seed"]) == pair]
        for row, offset, marker, color in ((buy, -0.13, "o", UPSTREAM),
                                          (sell, 0.13, "s", "#B15424")):
            median, tail = (100 * float(row[key]) for key in ("ratio_p50", "ratio_p99"))
            fraction.vlines(pos + offset, median, tail, color=color, alpha=0.58, linewidth=1.15)
            fraction.scatter(pos + offset, median, marker=marker, color=color, s=24, zorder=3)
            fraction.scatter(pos + offset, tail, marker="_", color=color, s=32, zorder=3)

        up = sum(int(row["upstream_comparisons"]) for row in (buy, sell))
        inc = sum(int(row["incremental_comparisons"]) for row in (buy, sell))
        comparisons.vlines(pos, inc, up, color="#92A6AD", linewidth=1.3)
        comparisons.scatter(pos, up, marker="o", color=UPSTREAM, s=30, zorder=3)
        comparisons.scatter(pos, inc, marker="D", color=INCREMENTAL, s=27, zorder=3)

    for ax in (fraction, comparisons):
        ax.set_yscale("log")
        ax.set_xlim(-0.44, 6.44)
        ax.set_xticks(POSITIONS, TICKS)
        ax.tick_params(axis="x", length=0, pad=6)
        ax.tick_params(axis="y", which="minor", length=0)
        ax.grid(axis="y", color="#DFE6EA", linewidth=0.75)
        ax.set_axisbelow(True)
    fraction.set_title("(a) Share of orders temporarily removed", loc="left", pad=8)
    fraction.set_ylabel(r"$k/\max(n,1)$ (log scale)")
    fraction.set_ylim(0.15, 36)
    fraction.set_yticks([0.2, 0.5, 1, 2, 5, 10, 20])
    fraction.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}%"))
    comparisons.set_title("(b) Comparisons during restore", loc="left", pad=8)
    comparisons.set_ylabel("Comparator calls (log scale)")
    comparisons.set_ylim(2100, 14_000_000)
    comparisons.set_yticks([10_000, 100_000, 1_000_000, 10_000_000])
    comparisons.yaxis.set_major_formatter(FuncFormatter(
        lambda value, _: f"{value / 1_000_000:g}M" if value >= 1_000_000 else f"{value / 1000:g}k"))
    for ax, items in ((fraction, (("Buy side", "o", UPSTREAM), ("Sell side", "s", "#B15424"))),
                      (comparisons, (("Upstream heapify", "o", UPSTREAM),
                                     ("Incremental heappush", "D", INCREMENTAL)))):
        handles = [Line2D([], [], label=label, marker=marker, color=color, linestyle="None")
                   for label, marker, color in items]
        ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.20), ncol=2)
    fig.text(0.107, 0.089, "Panel (a) shows the median marker and 99th-percentile cap.", color="#43576A")
    fig.text(0.107, 0.042, "Apple M5 · seeds 11 and 29 · instrumented diagnostic · log axes.",
             color="#43576A")
    fig.savefig(OUTPUT / "heap-mechanism-pilot.png", dpi=300)
    fig.savefig(OUTPUT / "heap-mechanism-pilot.pdf", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT.parent.parent / "P11-heap.csv"
    rows = read_pairs(source)
    with (OUTPUT / "heap-mechanism-pilot.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    render(rows)
    print(f"{len(rows)} matched side summaries from SHA-256 {hashlib.sha256(source.read_bytes()).hexdigest()}")
