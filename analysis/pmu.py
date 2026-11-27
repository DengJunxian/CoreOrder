"""Qualify sealed perf counters without changing the measured checkout."""

import hashlib
import json
import re
from pathlib import Path

from coreorder.measurement import pmu_receipt
from experiments.protocol import file_hash
from validation.io import read

POLICY = "coreorder-pmu-v1"
MIN_RUNNING_PERCENT = 95.0
SCOPE = "Python worker lifetime and inherited tasks; raw unscaled counts"
# perf 6.8.12 drops the :u display suffix on these two HW_CACHE aliases.
# Only allow that spelling when the sealed command requested the explicit :u event.
L1_ALIASES = {"L1-dcache-loads:u": "L1-dcache-loads", "L1-dcache-load-misses:u": "L1-dcache-load-misses"}
WORK_FIELDS = ("orders", "cancels", "expirations", "executions", "market_steps", "native_rows")
NATIVE_WORK_FIELDS = ("agent_calls", "decision_rows", "gauss_api_calls")


def locked_quality(perf_sha256, kernel):
    return {"policy": POLICY, "min_running_percent": MIN_RUNNING_PERCENT, "perf_sha256": perf_sha256, "kernel": kernel,
            "analysis_sha256": {name: file_hash(Path(__file__).with_name(name))
                                for name in ("pmu.py", "report.py", "figures.py")}}


def result(reasons, **details):
    return {"status": "INELIGIBLE" if reasons else "QUALIFIED", "policy": POLICY, "reasons": reasons, **details}


def check_capture(raw, receipt, launch, events, perf_sha256):
    """Check the actual perf output and command. This alone gives no formal admission."""
    reasons, coverage = [], []
    raw_hash = file_hash(raw) if raw.is_file() else None
    if raw_hash is None:
        return result(["missing_perf_csv"])

    command = launch.get("command", [])
    prefix = ["stat", "--no-big-num", "--no-scale", "-x", ";", "-o", str(raw.resolve())]
    event_args = [arg for event in events for arg in ("-e", event)]
    prefix += [*event_args, "--"]
    child = command[1 + len(prefix):]
    if (command[1:1 + len(prefix)] != prefix or child[1:4] != ["-m", "coreorder", "run"]
            or "--_measurement-child" not in child or "--mode" not in child
            or child[child.index("--mode") + 1:child.index("--mode") + 2] != ["pmu"]):
        reasons.append("wrong_perf_command_or_scope")
    if not command or not Path(command[0]).is_absolute() or not Path(command[0]).is_file():
        reasons.append("missing_perf_executable")
    elif file_hash(Path(command[0])) != perf_sha256:
        reasons.append("wrong_perf_executable")
    if launch.get("status") != "PASS" or type(launch.get("exit_code")) is not int or launch["exit_code"] != 0:
        reasons.append("perf_nonzero_exit")
    parsed = pmu_receipt(raw, events, launch)
    if receipt != parsed or receipt.get("scope") != SCOPE:
        reasons.append("pmu_receipt_differs_from_csv")
    if parsed["status"] != "PASS":
        reasons.append("perf_parse_or_collection_failed")

    rows = parsed["rows"]
    if len(rows) != len(events):
        reasons.append("missing_event" if len(rows) < len(events) else "extra_or_duplicate_event")
    for expected, observed in zip(events, rows):
        if observed["event"] not in (expected, L1_ALIASES.get(expected, expected)):
            reasons.append(f"wrong_event:{expected}")
        if type(observed["count"]) is not int or not 0 <= observed["count"] < 2**64 or observed["unit"] != "":
            value = observed["reported_value"]
            reason = {"<not supported>": "not_supported", "<not counted>": "not_counted"}.get(value, "invalid_count")
            reasons.append(f"{reason}:{expected}")
        running = re.fullmatch(r"[0-9]+", observed["runtime_ns"]) and int(observed["runtime_ns"]) > 0
        if not running:
            reasons.append(f"invalid_running_time:{expected}")
        percent = observed["percent_running"]
        number = float(percent) if re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,2})?", percent) else None
        if number is None or not 0 <= number <= 100:
            reasons.append(f"invalid_running_coverage:{expected}")
        elif number < MIN_RUNNING_PERCENT:
            reasons.append(f"low_running_coverage:{expected}")
        coverage.append({"requested": expected, "observed": observed["event"], "percent_running": number,
                         "multiplexed": number < 100 if running and number is not None and 0 <= number <= 100 else None})
    return result(reasons, coverage=coverage, perf_csv_sha256=raw_hash)


def qualify_attempt(protocol, row, attempt, receipts):
    """Apply the frozen PMU policy after the report has verified G3 and the V01 binding."""
    policy = protocol.lock.get("PMU_quality", {})
    if (not isinstance(policy, dict) or not policy.get("kernel")
            or not isinstance(policy.get("perf_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", policy["perf_sha256"])
            or policy != locked_quality(policy["perf_sha256"], policy["kernel"])):
        return result(["missing_or_different_frozen_pmu_policy"])
    events = row["events"]
    groups = protocol.lock["primary_x86"]["actual_pmu_events"] or {}
    if (not protocol.plan["diagnostics"]["PMU_enabled"] or not events or not all(e.endswith(":u") for e in events)
            or events != groups.get(row["event_group"]) or len(events) != len(set(events))):
        return result(["unqualified_event_group"])

    record = attempt["record"]
    directory = attempt["directory"] / "core"
    binding = record["validation"]
    if receipts is None or binding is None:
        return result(["missing_v01_binding"])
    v01 = receipts / "raw" / binding["case_id"] / binding["run_id"]
    try:
        launch = read(directory / "launch/command.json")
        receipt = read(directory / "pmu.json")
        raw = directory / "perf-stat.csv"
        quality = check_capture(raw, receipt, launch, events, policy["perf_sha256"])
        reasons = quality["reasons"]
        if receipt != record["metrics"].get("pmu"):
            reasons.append("pmu_receipt_differs_from_sealed_metrics")

        runtime = record["manifest"]
        environment = read(directory / "environment.json")
        if (environment["kernel"] != policy["kernel"] or environment["architecture"] not in ("x86_64", "AMD64")
                or environment["host_id"] != runtime["host_id"] or environment["git_sha"] != runtime["git_sha"]
                or environment["dirty"] is not False or launch["dirty"] is not False
                or launch["git_sha"] != runtime["git_sha"]):
            reasons.append("wrong_pmu_host_or_source")
        proof = read(v01 / "seal.json")["files_sha256"]
        v01_record_bytes = (v01 / "record.json").read_bytes()
        if (proof["validation-receipt.json"] != binding["sha256"]
                or file_hash(v01 / "validation-receipt.json") != binding["sha256"]
                or hashlib.sha256(v01_record_bytes).hexdigest() != proof["record.json"]):
            reasons.append("v01_workload_evidence_differs")
        else:
            baseline = json.loads(v01_record_bytes)["metrics"]
            fields = WORK_FIELDS + NATIVE_WORK_FIELDS if row["settings"]["backend"].startswith("native") else WORK_FIELDS
            work = {key: record["metrics"].get(key) for key in fields}
            if any(type(value) is not int or value < 0 or value != baseline.get(key) for key, value in work.items()):
                reasons.append("v01_financial_workload_differs")
            else:
                quality["financial_work"] = work
        quality["status"] = "INELIGIBLE" if reasons else "QUALIFIED"
        return quality
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        return result(["unreadable_pmu_or_v01_evidence"])
