"""Project frozen row counts using R4A pilot costs. This is planning, not formal inference."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

from validation.io import write

PLAN = Path("configs/experiments")


def jsonl(path):
    with path.open(encoding="utf8") as source:
        return [json.loads(line) for line in source]


rows = jsonl(Path(sys.argv[1]))
timing = [r for r in rows if r["kind"] == "timing" and r["status"] == "PASS"]
assert len(timing) == 24, "R4A timing census incomplete"
overhead = max(r["elapsed_s_driver"] - r["core_metrics"]["process_wall_s"]
               for r in timing if "elapsed_s_driver" in r)

sample = defaultdict(list)
by_workload = defaultdict(list)
metrics = ("orders", "cancels", "expirations", "executions", "market_steps")
checks = defaultdict(set)
for row in timing:
    assert row["seed"] in (11, 29)
    key = (row["workload"], row["backend"], row["heap"], row["workers"], row["layout"])
    m = row["core_metrics"]
    seconds = row.get("elapsed_s_driver", m["process_wall_s"] + overhead)
    sample[key].append(seconds)
    by_workload[row["workload"]].append(seconds)
    status = row["core_status"]
    checks[(row["config_sha256"], row["seed"])].add(
        (status["final_state_hash"], status["rng_hash"], *(m[f] for f in metrics)))
assert all(len(states) == 1 for states in checks.values())

frozen_timing = jsonl(PLAN / "runlist-timing.jsonl")
time_by_stage = Counter()
exact = Counter()
proxies = Counter()
raw_bytes = 0
for row in frozen_timing:
    workload = row["workload"]
    settings = row["settings"]
    # W0-H upstream is byte-identical to W0-CI2002 under the same heap setting.
    if workload == "W0-H" and settings["book_restore"] == "upstream":
        workload = "W0-CI2002"
    key = (workload, settings["backend"], settings["book_restore"], settings["workers"],
           None if settings["layout"] == "not_applicable" else settings["layout"])
    time_by_stage[row["phase"]] += max(sample.get(key, by_workload[workload]))
    if key in sample:
        exact[row["phase"]] += 1
    else:
        proxies[row["phase"]] += 1
    raw_bytes += max(r["raw_bytes"] for r in timing if r["workload"] == workload)

v01 = jsonl(PLAN / "runlist-V01.jsonl")
validation = [r for r in rows if r["kind"] in ("validation", "oracle")]
oracle = next(r for r in validation if r["id"] == "oracle-C01b-normal-11")
c01_cells = next(r for r in validation if r["id"] == "validation-C01b-normal-11-py-process-incremental-na-4")
c01_proxy = 60 * oracle["elapsed_s_driver"] + 360 * c01_cells["elapsed_s_driver"]

write(Path(sys.argv[2]), {
    "scope": "R4A seed 11/29 planning projection; no confidence interval or completion guarantee",
    "row_counts": {"C01": len(jsonl(PLAN / "runlist-C01.jsonl")), "V01": len(v01),
                   "timing": len(frozen_timing), "E05": len(jsonl(PLAN / "runlist-E05.jsonl"))},
    "timing": {"warmups": sum(r["warmup"] for r in frozen_timing), "minutes": {k: v / 60 for k, v in time_by_stage.items()},
               "total_minutes": sum(time_by_stage.values()) / 60, "exact_config_rows": exact,
               "workload_proxy_rows": proxies, "recovered_outer_overhead_proxy_s": overhead,
               "raw_bytes_at_sample_workload_max": raw_bytes},
    "C01_C01b_only_proxy_minutes": c01_proxy / 60,
    "V01_measured_cases": [{k: r[k] for k in ("id", "status", "elapsed_s_driver", "raw_bytes")}
                           for r in validation if r["workload"] != "C01b-normal"],
    "matching_config_seed_groups": len(checks),
})
