"""Export the P11 raw-to-table mapping without fitting or selecting workloads."""

from collections import Counter
import csv
import json
from pathlib import Path
import pstats
import sys

import numpy as np
from validation.io import read, write


def dataset(path, rows):
    with path.open("x", newline="") as file:
        table = csv.DictWriter(
            file, fieldnames=list(dict.fromkeys(key for r in rows for key in r)), lineterminator="\n",
        )
        table.writeheader()
        table.writerows(rows)


def quantiles(values):
    if not values:
        return dict.fromkeys(("min", "p50", "p90", "p99", "max"))
    return dict(zip(("min", "p50", "p90", "p99", "max"),
                    map(float, np.quantile(values, (0, 0.5, 0.9, 0.99, 1))), strict=True))


def main(root, output):
    output.mkdir()
    ledger = root / "chronological-final.json"
    receipts = read(ledger if ledger.is_file() else root / "chronological.json")
    timing, heap, rows, phases, profiles = [], [], [], [], []
    for attempt in receipts:
        path = Path(attempt["run"])
        tag = {key: attempt[key] for key in ("case", "workload", "seed", "backend", "restore", "purpose", "status")}
        summary = attempt.get("summary", {})
        timing.append({**tag, "process_elapsed_s": attempt["process_elapsed_s"],
                       "timeout_s": attempt["timeout_s"], "simulation_s": summary.get("simulation_s"),
                       "setup_s": summary.get("setup_s"), "orders": summary.get("orders_admitted"),
                       "event_hash": summary.get("event_hash"), "state_hash": summary.get("state_hash"),
                       "rng_hash": summary.get("rng_hash")})
        if attempt["status"] != "PASS":
            continue
        if (path / "heap.json").is_file():
            raw = read(path / "heap.json")
            for side in ("buy", "sell"):
                records = raw[side]["rows"]
                assert len(records) == raw[side]["restore_calls"] == raw["restore_calls"]
                assert all(r["heap_length_before"] == r["heap_length_remaining"] + r["popped_count"]
                           for r in records)
                assert all(r["restore_fraction"] == r["popped_count"] / max(r["heap_length_before"], 1)
                           for r in records)
                distributions = {short: [r[field] for r in records] for short, field in (
                    ("n", "heap_length_before"), ("h", "heap_length_remaining"),
                    ("k", "popped_count"), ("ratio", "restore_fraction"),
                )}
                heap.append({**tag, "side": side, "restore_calls": len(records),
                             "comparison_calls": raw["restore_order_lt_calls"][side],
                             **{f"sum_{k}": sum(v) for k, v in distributions.items() if k != "ratio"},
                             **{f"{k}_{q}": value for k, v in distributions.items()
                                for q, value in quantiles(v).items()}})
                rows.extend(({**tag, "side": side, **row} for row in records))
            if tag["restore"] == "upstream":
                assert raw["heapq_calls"] == {"heapify": 2 * raw["restore_calls"], "heappush": 0}
            else:
                expected = sum(row["popped_count"] for side in ("buy", "sell") for row in raw[side]["rows"])
                assert raw["heapq_calls"] == {"heapify": 0, "heappush": expected}
        if (path / "phases.json").is_file() and tag["purpose"] == "phases":
            timing_map = read(path / "phases.json")
            phases.extend(({**tag, "phase": name, "seconds": elapsed / 1e9,
                            "calls": timing_map["calls"][name], "sim_wall_s": summary["simulation_s"]}
                           for name, elapsed in timing_map["nanoseconds"].items()))
        if (path / "profile.prof").is_file():
            stats = pstats.Stats(str(path / "profile.prof"))
            for (file, line, method), (primitive, calls, self_s, cum_s, _) in stats.stats.items():
                profiles.append({**tag, "file": file, "line": line, "method": method,
                                 "calls": calls, "self_s": self_s, "inclusive_s": cum_s,
                                 "profile_total_s": stats.total_tt})

    for workload, seed in sorted({(row["workload"], row["seed"]) for row in heap}):
        selected = [row for row in rows if (row["workload"], row["seed"]) == (workload, seed)]
        def flow(mode):
            return [{k: row[k] for k in ("side", "market_id", "step", "heap_length_before",
                                         "heap_length_remaining", "popped_count", "restore_fraction")}
                    for row in selected if row["restore"] == mode]
        assert flow("upstream") == flow("incremental"), (workload, seed)

    for name, data in (
        ("runs", timing), ("heap-summary", heap), ("heap-events", rows),
        ("phase-spans", phases), ("cprofile", profiles),
    ):
        if data:
            dataset(output / f"{name}.csv", data)
    summary = {"attempts": dict(Counter(r["status"] for r in receipts)),
               "purposes": dict(Counter(r["purpose"] for r in receipts)),
               "heap_observations": len(rows)}
    write(output / "summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
