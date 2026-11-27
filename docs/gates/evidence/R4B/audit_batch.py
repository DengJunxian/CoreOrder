"""Recheck immutable C01/V01 evidence and publish an index for human review."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
from pathlib import Path

from experiments.evidence import validation_binding
from experiments.protocol import Protocol, condition, file_hash, is_oracle
from experiments.run import read_batch, stage_rows
from validation.io import read, write


def audit(plan, root, output):
    protocol = Protocol(plan)
    batch = read(root / "batch.json")
    stage = batch["stage"]
    assert stage in ("C01", "V01") and not batch["selected_cases"]
    rows = stage_rows(protocol, stage, [])
    batch, attempts = read_batch(root, protocol, rows)
    runtime = batch["runtime"]
    census = Counter()
    per_workload = defaultdict(Counter)
    accepted = {}
    index = []
    for row in rows:
        case = row["id"]
        attempt = attempts.get(case)
        item = {"case_id": case, "workload": row["workload"], "seed": row["seed"],
                "settings": row["settings"], "oracle": is_oracle(row)}
        if attempt is None:
            item.update(status="NOT_RUN", reason="no sealed attempt")
        else:
            record = attempt["record"]
            status = record["status"]
            directory = attempt["directory"]
            item.update(status=status["status"], reason=status["reason"], censoring=status["censoring"],
                        run_id=status["run_id"], raw_directory=directory.relative_to(root).as_posix(),
                        elapsed_s=attempt["elapsed_s"], launch=record["command"],
                        seal_sha256=file_hash(directory / "seal.json"),
                        raw_bytes=sum((directory / file).stat().st_size for file in attempt["files_sha256"]))
            if not is_oracle(row) and status["status"] == "PASS":
                expected = condition(protocol.workloads[row["workload"]], row, runtime)
                receipt, binding = validation_binding(attempt, expected, attempts)
                accepted[case] = binding
                item.update(receipt=receipt, receipt_sha256=binding["sha256"])
            if status["status"] != "PASS":
                reproducer = directory / "core/first-divergence/first_divergence.json"
                if reproducer.is_file():
                    item["first_divergence"] = read(reproducer)
        census[item["status"]] += 1
        per_workload[row["workload"]][item["status"]] += 1
        index.append(item)
    result = {
        "scope": "candidate correctness evidence; G3 authorization is separate",
        "stage": stage, "runtime": runtime, "batch_digest": file_hash(root/"batch.json"),
        "protocol_hash": protocol.identity, "schedule_digest": batch["schedule_sha256"],
        "raw_root": str(root), "census": dict(census), "per_workload": dict(per_workload),
        "planned_references": sum(map(is_oracle, rows)),
        "planned_candidates": sum(not is_oracle(row) for row in rows),
        "accepted": accepted,
        "elapsed_s": sum(item.get("elapsed_s", 0) for item in index),
        "raw_bytes": sum(item.get("raw_bytes", 0) for item in index),
        "records": index,
    }
    write(output, result)
    print(stage, dict(census), f"{len(accepted)} candidate bindings", f'{result["elapsed_s"]:.2f}s',
          f'{result["raw_bytes"]} bytes')


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    for name in ("plan", "raw", "output"):
        parser.add_argument(name, type=Path)
    opts = parser.parse_args()
    audit(opts.plan, opts.raw.resolve(), opts.output)
