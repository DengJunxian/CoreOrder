"""Check the candidate, target identity and sealed V01 without starting experiments."""
from collections import Counter
from pathlib import Path
import json
import os
import sys

from experiments.evidence import inspect_environment, validation_binding
from experiments.protocol import Protocol, condition, is_oracle
from experiments.replay import replay_command
from experiments.run import exclusive_host, parent_core_args, read_batch, stage_rows

plan_path, staged_path, v01_path = map(Path, sys.argv[1:])
candidate, staged = Protocol(plan_path), Protocol(staged_path)
env, runtime = inspect_environment(candidate, native=True)
target = candidate.lock["primary_x86"]
assert runtime["dirty"] is False and runtime["git_sha"] == target["code_sha"]
assert runtime["host_id"] == target["host_id"] and runtime["environment_sha256"] == target["environment_sha256"]
assert runtime["native_sha256"] == target["native_module"]["sha256"]
assert sorted(os.sched_getaffinity(0)) == target["affinity"]["guest_cpus"]
assert all(value == "1" for value in env["external_threads"].values())
assert candidate.rows == staged.rows

v01_rows = stage_rows(staged, "V01", [])
with exclusive_host(False, v01_path):
    batch, attempts = read_batch(v01_path, staged, v01_rows)
    assert batch["runtime"] == runtime and len(attempts) == len(v01_rows)

    approvals = candidate.lock["approval"]["V01_receipts"]
    assert set(approvals) == {row["id"] for row in v01_rows if not is_oracle(row)}
    validated = {}
    for row in v01_rows:
        case = row["id"]
        assert attempts[case]["record"]["status"]["status"] == "PASS"
        if not is_oracle(row):
            expected = condition(candidate.workloads[row["workload"]], row, runtime)
            checked = validation_binding(attempts[case], expected, attempts, approvals[case])
            assert checked[0]["reference_case_id"] == row["reference"]
            validated[case] = checked

assert all(row["v01"] in validated for row in candidate.rows["timing"])
for row in candidate.rows["E05"]:
    workload = candidate.workloads[row["workload"]]
    if row["phase"] == "E05-replay":
        replay_command(candidate, row, Path("."), validated)
    else:
        expected = condition(workload, row, runtime)
        assert any(item[0]["identity"] == expected for item in validated.values())
        if row["phase"] == "E05-PMU":
            parent_core_args(row, workload, Path("."), "0" * 32, 30, "pmu", None, candidate)

admission = {}
for stage in ("timing", "E05"):
    try:
        admission[stage] = {"eligible_rows": len(stage_rows(candidate, stage, []))}
    except ValueError as error:
        admission[stage] = {"eligible_rows": 0, "reason": str(error)}
try:
    candidate.approval(runtime)
except ValueError as error:
    admission["approval"] = str(error)

print(json.dumps({
    "scope": "read-only admission, no experiment launch",
    "runtime": runtime,
    "workload_digests_verified": len(candidate.workloads),
    "candidate_identity": candidate.identity,
    "candidate_state": candidate.plan["status"],
    "locked_for_execution": candidate.lock["locked_for_execution"],
    "effective_lock_sha256": candidate.plan["protocol_lock_hash"],
    "formal_code_sha": candidate.plan["formal_code_sha"],
    "authorized_formal_rows": len(candidate.plan["authorized_formal_runs"]),
    "gates": {key: candidate.lock["approval"][key] for key in ("G0", "G1", "G2", "G3")},
    "signoffs": {key: candidate.lock["approval"][key] for key in ("A_signoff", "E_signoff")},
    "validation": {"attempts": len(attempts), "candidate_receipts": len(validated),
                   "oracle_attempts": len(attempts) - len(validated),
                   "status": dict(Counter(row["record"]["status"]["status"] for row in attempts.values()))},
    "planned_schedule": {stage: dict(Counter(row["phase"] for row in candidate.rows[stage]))
                         for stage in ("timing", "E05")},
    "formal_admission": admission,
}, indent=2))
