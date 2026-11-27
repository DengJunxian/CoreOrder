"""Compute validation-only planning cost from full x86 rehearsals."""
from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path

from experiments.protocol import Protocol, is_oracle
from validation.io import read, write


def project(original, revised, calibration, output, additional):
    samples = {(row["workload"], row["oracle"]): row
               for source in (calibration, *additional) for row in read(source)}
    results = {}
    for name, base in (("P12_original", original), ("R4B_approved", revised)):
        workload = defaultdict(lambda: {"attempts": 0, "seconds": 0, "bytes": 0})
        missing = []
        for row in Protocol(base).rows["V01"]:
            key = row["workload"]
            sample = samples.get(("W0-CI2002" if key == "W0-H" else key, is_oracle(row)))
            item = workload[key]
            item["attempts"] += 1
            if sample is None or sample["status"]["status"] != "PASS":
                missing.append(row["id"])
                continue
            item["seconds"] += sample["elapsed_s"]
            item["bytes"] += sample["bytes"]
        results[name] = {
            "known_proxy_minutes": sum(item["seconds"] for item in workload.values()) / 60,
            "known_proxy_raw_bytes": sum(item["bytes"] for item in workload.values()),
            "workloads": dict(workload), "rows_without_passing_proxy": missing,
        }
    write(output, {"scope": "same workload and role, single successful pilot observation; no formal measurement",
                   "V01_budget_minutes": 80, "estimates": results})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    for name in ("original", "revised", "rehearsal", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--additional", type=Path, action="append", default=[])
    args = parser.parse_args()
    project(args.original, args.revised, args.rehearsal, args.output, args.additional)
