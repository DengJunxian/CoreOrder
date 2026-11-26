"""Measure full validation costs with fixed pilot seeds via the production receipt path."""
from pathlib import Path
import os
import resource
import sys
from time import perf_counter

from experiments.evidence import inspect_environment
from experiments.protocol import Protocol, is_oracle
from experiments.run import attempt, exclusive_host
from validation.io import write

root = Path(sys.argv[1]).resolve()
root.mkdir(exist_ok=False)
protocol = Protocol()
assert not protocol.active
actual, runtime = inspect_environment(protocol, native=True)
assert runtime["git_sha"] == sys.argv[2] and runtime["dirty"] is False
assert sorted(os.sched_getaffinity(0)) == [0, 2, 4, 6, 8, 10, 12, 14]
assert all(value == "1" for value in actual["external_threads"].values())
write(root / "candidate-identity.json", runtime)
write(root / "environment.json", actual)
resource.setrlimit(resource.RLIMIT_AS, (7 * 1024**3, resource.getrlimit(resource.RLIMIT_AS)[1]))
cases = [
    ("W0-CI2002", 11, "native-serial", "upstream", 1, "aos"),
    ("W1-H", 11, "py-seq", "incremental", 1, "not_applicable"),
    ("W2-H", 11, "py-seq", "incremental", 1, "not_applicable"),
    ("W1-SMALL-BATCH", 11, "native-serial", "incremental", 1, "aos"),
    ("W2-MEDIUM-BATCH", 29, "native-parallel", "incremental", 4, "soa"),
    ("W3-LARGE-MULTI", 11, "native-parallel", "incremental", 4, "aos"),
]
if len(sys.argv) > 3:
    cases = [item for item in cases if item[0] == sys.argv[3]]
    if len(cases) != 1:
        raise ValueError("unknown supplemental rehearsal workload")
held = {}
summaries = []
deadline = perf_counter() + (300 if len(sys.argv) > 3 else 720)
with exclusive_host(False, root):
    for workload, seed, backend, heap, workers, layout in cases:
        assert seed in protocol.plan["pilot_seeds"] and seed not in protocol.plan["formal_seeds"]
        row = next(r for r in protocol.rows["V01"] if not is_oracle(r) and
                   (r["workload"], *[r["settings"][k] for k in ("backend", "book_restore", "workers", "layout")])
                   == (workload, backend, heap, workers, layout))
        original = protocol.index[row["reference"]]
        ref = {**original, "id": f"r4b-rehearsal-oracle-{workload}-{seed}", "seed": seed}
        variant = {**row, "id": f"r4b-rehearsal-{workload}-{seed}", "seed": seed, "reference": ref["id"]}
        for item in (ref, variant):
            remain = min(item["timeout_s"], deadline - perf_counter())
            if remain <= 0:
                break
            result = attempt(protocol, item, runtime, "r4b-validation-rehearsal", root, remain, held, None)
            held[item["id"]] = result
            status = result["record"]["status"]
            evidence = result["files_sha256"]
            data = {"id": item["id"], "workload": workload, "seed": seed, "oracle": is_oracle(item),
                    "status": status, "elapsed_s": result["elapsed_s"],
                    "bytes": sum((result["directory"] / name).stat().st_size for name in evidence),
                    "directory": str(result["directory"])}
            summaries.append(data)
            print(item["id"], status["status"], f'{result["elapsed_s"]:.3f}', data["bytes"], status.get("reason"),
                  flush=True)
write(root / "summary.json", summaries)
