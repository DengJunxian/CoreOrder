"""Check the provisional schedule and bytes without launching an experiment."""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import sys

from coreorder.config import incremental_workload
from coreorder.schema import validate_record

BASE = Path("configs/experiments")


def read(file):
    return json.loads(file.read_bytes())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rows(name):
    return [json.loads(line) for line in (BASE / f"runlist-{name}.jsonl").read_text().splitlines()]


def verify():
    plan, lock = (read(BASE / name) for name in ("frozen.json", "protocol_lock.json"))
    assert plan["status"] == "BLOCKED" and lock["state"] == "BLOCKED"
    assert plan["runnable"] is lock["locked_for_execution"] is False
    assert plan["authorized_formal_runs"] == [] and plan["formal_code_sha"] is None
    assert lock["approval"]["V01_accepted"] == 0
    for item in (BASE / "P12-SHA256SUMS").read_text().splitlines():
        digest, path = item.split("  ", 1)
        assert sha((BASE / path).read_bytes()) == digest
    for path, digest in lock["candidate_files_sha256"].items():
        assert sha((BASE / path).read_bytes()) == digest

    workloads = plan["workloads"]
    for record in workloads.values():
        payload = Path(record["path"]).read_bytes()
        settings = json.loads(payload)
        validate_record("workload", settings)
        assert sha(payload) == record["input_sha256"] == record["effective_sha256"]["upstream"]
        translated = (json.dumps(incremental_workload(settings), ensure_ascii=False, allow_nan=False) + "\n").encode()
        assert sha(translated) == record["effective_sha256"]["incremental"]
    assert workloads["W0-H"]["input_sha256"] == workloads["W0-CI2002"]["input_sha256"]
    assert workloads["W0-CI2002"]["path"] == "vendor/pams/samples/CI2002/config.json"

    types = ("C01", "V01", "timing", "E05")
    entries = {name: rows(name) for name in types}
    assert {name: len(values) for name, values in entries.items()} == {"C01": 420, "V01": 170, "timing": 527, "E05": 108}
    assert Counter(row["phase"] for row in entries["E05"]) == {"E05-PMU": 24, "E05-profile": 4, "E05-replay": 80}
    identifiers = set()
    for values in entries.values():
        for row in values:
            assert row["id"] not in identifiers
            identifiers.add(row["id"])
            assert row["status"] == "NOT_RUN" and row["runnable"] is False and row["run_id"] is None
            validate_record("run_config", {**row["settings"], "seed": row["seed"]})
            assert row["workload"] in workloads
    v01 = {row["id"]: row for row in entries["V01"]}
    oracles = [row for row in v01.values() if row.get("runner") == "verified vendor oracle"]
    assert len(oracles) == 30
    for row in oracles:
        assert row["settings"]["backend"] == "py-seq" and row["settings"]["book_restore"] == "upstream"
    for row in v01.values():
        if "reference" in row:
            reference = v01[row["reference"]]
            assert row["validation_run_id"] is None
            assert reference["seed"] == row["seed"]
            assert workloads[reference["workload"]]["input_sha256"] == workloads[row["workload"]]["input_sha256"]

    groups = {g["id"]: g for g in plan["pairing_groups"]}
    blocks = defaultdict(list)
    warmups = Counter()
    for row in entries["timing"]:
        candidate = v01[row["v01"]]
        assert row["settings"] == candidate["settings"] and row["seed"] == candidate["seed"]
        assert workloads[row["workload"]]["input_sha256"] == workloads[candidate["workload"]]["input_sha256"]
        if row["warmup"]:
            assert row["block_id"] is None and row["order_position"] is None
            warmups[(row["group"], row["variant"])] += 1
        else:
            blocks[row["block_id"]].append(row)
    assert len(blocks) == 120 and len(warmups) == 31 and set(warmups.values()) == {2}
    assert sum(map(len, blocks.values())) == 465
    for block, items in blocks.items():
        group = groups[items[0]["group"]]
        variants = [v["id"] for v in group["variants"]]
        seed = int(sha(f'{plan["order_master_seed"]}/{block}'.encode())[:13], 16)
        random.Random(seed).shuffle(variants)
        assert variants == [i["variant"] for i in items]
        assert all(i["order_seed"] == seed and i["order_position"] == index
                   for index, i in enumerate(items, 1))
    for group in groups.values():
        if group["experiment"] in ("H01", "E03"):
            modes = {v["id"]: v for v in group["variants"]}
            change = "book_restore" if group["experiment"] == "H01" else "layout"
            for left, right in group["ordered_pairs"]:
                a, b = modes[left], modes[right]
                assert {key for key in a if a[key] != b[key]} == {"id", change}
        if group["experiment"] in ("E02", "E03"):
            assert all(v["book_restore"] == "incremental" for v in group["variants"])
    total = sum(plan["primary"]["stage_budgets_minutes"].values())
    assert total == 460 and total + plan["primary"]["rerun_reserve_minutes"] == 480
    assert plan["primary"]["stage_budgets_minutes"]["V01"] == 80
    mac = plan["mac_plan"]
    assert sum(mac[k] for k in ("environment_and_chain", "semantic_validation", "representative_checks", "reserve")) == 60
    assert plan["statistics"]["unit"] == "seed" and plan["statistics"]["bootstrap_resamples"] == 10000
    assert [item["id"] for item in plan["optional"] if item["enabled"]] == []
    print("PASS candidate bytes, workload hashes, 8 groups, 120 randomized blocks, 527 timing/warmup rows,")
    print("420 C01 rows, 140 V01 candidate cells + 30 oracles, 108 E05 rows, primary 480 min, Mac 60 min.")
    print("G3 BLOCKED. No study row is executable.")


if __name__ == "__main__":
    verify()
