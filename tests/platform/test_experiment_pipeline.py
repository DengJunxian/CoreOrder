"""R2B protocol checks and a small real PAMS chain. Statistical examples are synthetic tests."""

import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from analysis.report import compare_groups
from experiments.evidence import evidence_files, read_attempts
from experiments.protocol import DEFAULT, Protocol, file_hash
from experiments.run import stage_rows

ROOT = DEFAULT.parents[1]
HAS_NATIVE = bool(list((ROOT / "build").glob("_coreorder_fcn*")))


def run_cli(module, *args):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "build")}
    return subprocess.run([sys.executable, "-m", module, *map(str, args)], cwd=ROOT, capture_output=True,
                          text=True, env=env, timeout=100)


def load(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value) + "\n")


def test_candidate_protocol_and_gate(tmp_path):
    protocol = Protocol()
    assert {kind: len(rows) for kind, rows in protocol.rows.items()} == {"C01": 420, "V01": 170, "timing": 527, "E05": 108}
    for stage in ("C01", "V01"):
        candidate = next(row for row in protocol.rows[stage] if row.get("runner") != "verified vendor oracle")
        selected = stage_rows(protocol, stage, [candidate["id"]])
        assert [row["id"] for row in selected] == [candidate["reference"], candidate["id"]]
    result = run_cli("experiments.run", "--stage", "timing", "--output", tmp_path / "prohibited")
    assert result.returncode == 2 and "G3 BLOCKED" in result.stderr
    assert not (tmp_path / "prohibited").exists()


def test_schedule_rejects_digest_and_pairing_changes(tmp_path):
    target = shutil.copytree(DEFAULT, tmp_path / "plan")
    timing = target / "runlist-timing.jsonl"
    lines = [json.loads(line) for line in timing.read_text().splitlines()]
    wrong = next(row for row in lines if not row["warmup"])
    wrong["order_position"] += 1
    timing.write_text("".join(json.dumps(row) + "\n" for row in lines))
    with pytest.raises(ValueError, match="protocol digest mismatch"):
        Protocol(target)
    lock_file = target / "protocol_lock.json"
    lock = load(lock_file)
    lock["candidate_files_sha256"]["runlist-timing.jsonl"] = file_hash(timing)
    save(lock_file, lock)
    with pytest.raises(ValueError, match="invalid pairing/order"):
        Protocol(target)


@pytest.fixture(scope="module")
def pilot_raw(tmp_path_factory):
    if not HAS_NATIVE:
        pytest.skip("build the Release extension for the real pipeline test")
    output = tmp_path_factory.mktemp("r2b-pilot") / "batch"
    result = run_cli("experiments.run", "--stage", "pilot", "--budget-seconds", 90, "--output", output)
    assert result.returncode == 0, (result.stdout, result.stderr)
    return output


def test_real_pipeline_and_duplicate_resume(pilot_raw, tmp_path):
    first = read_attempts(pilot_raw)
    assert len(first) == 18
    assert len({attempt["record"]["manifest"]["run_id"] for attempt in first.values()}) == 18
    for attempt in first.values():
        record = attempt["record"]
        if record["metrics"]["measurement_mode"] == "timing":
            assert record["validation"]["run_id"] == record["manifest"]["validation_run_id"]
            assert record["status"]["validation_status"] == "PASS"
    for args, expected in (((), 2), (("--resume",), 0)):
        result = run_cli("experiments.run", "--stage", "pilot", "--budget-seconds", 90, "--output", pilot_raw, *args)
        assert result.returncode == expected, result.stderr
        assert read_attempts(pilot_raw) == first
    output = tmp_path / "report"
    result = run_cli("analysis.report", "--input", pilot_raw, "--output", output, "--development")
    assert result.returncode == 0, result.stderr
    report = load(output / "report.json")
    comparison = report["comparisons"][0]
    assert report["scope"] == "development-pilot" and report["counts"]["PASS"] == 18
    assert report["warmups_by_status"] == {"PASS": 2}
    assert len(comparison["blocks"]) == 4 and set(comparison["seed_effects"]) == {"11", "29"}
    assert all(effect["n_pairs"] == 2 for effect in comparison["seed_effects"].values())
    assert 0 < comparison["speedup_ci95"][0] <= comparison["speedup"] <= comparison["speedup_ci95"][1]
    assert comparison["parallel_efficiency"] == comparison["speedup"] / 2
    rejected = run_cli("analysis.report", "--input", pilot_raw, "--output", tmp_path / "formal")
    assert rejected.returncode == 2 and "scope must match" in rejected.stderr


@pytest.mark.parametrize(("fault", "reason"), [
    ("raw", "tampered raw data"), ("receipt", "validation receipt identity mismatch"),
    ("pairing", "raw schedule identity differs"), ("duplicate", "one immutable attempt"),
])
def test_report_rejects_damaged_records(pilot_raw, tmp_path, fault, reason):
    root = shutil.copytree(pilot_raw, tmp_path / "raw-copy")
    key = {"receipt": "pilot-validation-11-native-direct", "pairing": "pilot-C01b-normal-11-1-native-direct"}.get(
        fault, "pilot-warmup-native-direct",
    )
    directory = next((root / "raw" / key).iterdir())
    if fault == "duplicate":
        shutil.copytree(directory, directory.parent / ("c" * 32))
    else:
        artifact = directory / ("validation-receipt.json" if fault == "receipt" else "record.json")
        record = load(artifact)
        if fault == "receipt":
            record["identity"]["seed"] = 29
        elif fault == "pairing":
            record["manifest"]["order_position"] += 1
        else:
            record["metrics"]["simulation_s"] = 1
        save(artifact, record)
        if fault != "raw":
            seal = directory / "seal.json"
            index = load(seal)
            index["files_sha256"] = evidence_files(directory)
            save(seal, index)
    result = run_cli("analysis.report", "--input", root, "--output", tmp_path / "report", "--development")
    assert result.returncode == 2 and reason in result.stderr
    assert not (tmp_path / "report").exists()


def test_resume_preserves_interrupted_raw_and_continues(pilot_raw, tmp_path):
    root = shutil.copytree(pilot_raw, tmp_path / "interrupted")
    rows = load(root / "batch.json")["case_ids"]
    # Interrupt at the last profile, after all evidence required by timing has completed.
    path = next((root / "raw" / rows[-1]).iterdir())
    (path / "seal.json").unlink()
    result = run_cli("experiments.run", "--stage", "pilot", "--budget-seconds", 90, "--output", root, "--resume")
    assert result.returncode == 1, result.stderr
    recovered = read_attempts(root)[rows[-1]]
    assert recovered["directory"] == path and recovered["record"]["status"]["status"] == "FAIL"
    assert recovered["record"]["manifest"]["backend_effective"] is None
    assert len(list(path.glob("interrupted-record-*"))) == 1


def test_real_timeout_preserves_right_censoring(tmp_path):
    output = tmp_path / "timeout"
    run = run_cli("experiments.run", "--stage", "V01", "--case", "V01-reference-580231068a1b7175-101",
                  "--budget-seconds", 0.02, "--output", output)
    assert run.returncode == 1, (run.stdout, run.stderr)
    attempt, = read_attempts(output).values()
    record = attempt["record"]
    assert record["status"]["status"] == "TIMEOUT" and record["status"]["censoring"] == "right"
    assert record["manifest"]["backend_effective"] is None
    assert record["metrics"]["simulation_s"] is None
    assert load(attempt["directory"] / record["command"])["timeout_s"] == 0.02


@pytest.mark.skipif(not HAS_NATIVE, reason="build the Release extension for real C01")
def test_c01_accepts_real_zero_native_rows(tmp_path):
    output = tmp_path / "c01"
    case = "C01-C01f-M0-101-5"
    result = run_cli("experiments.run", "--stage", "C01", "--case", case, "--output", output)
    assert result.returncode == 0, (result.stdout, result.stderr)
    attempt = read_attempts(output)[case]
    assert attempt["record"]["status"]["validation_status"] == "PASS"
    assert attempt["record"]["metrics"]["native_rows"] == 0
    assert (attempt["directory"] / "validation-receipt.json").is_file()


def test_synthetic_seed_aggregation_and_incomplete_comparison():
    scope = "synthetic test"
    settings = {"workers": 1, "book_restore": "incremental", "layout": "aos", "backend": "native-serial"}
    group = {"id": "synthetic", "workload": scope, "experiment": "E02", "ordered_pairs": [("direct", "pool")],
             "variants": [{"id": "direct", **settings}, {"id": "pool", **settings, "backend": "native-parallel",
                                                        "workers": 2}]}
    rows = []
    seeds = [101, 202, 303, 404, 505]
    for index, seed in enumerate(seeds, 1):
        for repeat, ratio in enumerate((index / 2, index, index * 2), 1):
            for variant, time in (("direct", 10 * ratio), ("pool", 10.0)):
                rows.append({"host_id": "synthetic", "workload": scope, "seed": seed, "repeat": repeat,
                             "group": group["id"], "block_id": f"{seed}-{repeat}", "variant": variant,
                             "mode": "timing", "warmup": False, "status": "PASS",
                             "timings_ms": {"simulation_s": time}})
    stats = {"bootstrap_resamples": 10000, "bootstrap_seed": 73021, "confidence_level": 0.95}
    result, = compare_groups([group], rows, seeds, 3, stats)
    assert result["speedup"] == pytest.approx(math.prod(range(1, 6)) ** (1 / 5))
    assert result["parallel_efficiency"] == pytest.approx(result["speedup"] / 2)
    assert result["speedup_ci95"] == compare_groups([group], rows, seeds, 3, stats)[0]["speedup_ci95"]
    rows[-1].update(status="TIMEOUT", censoring="right")
    incomplete, = compare_groups([group], rows, seeds, 3, stats)
    assert incomplete["speedup"] is incomplete["speedup_ci95"] is None
    assert incomplete["blocks"][-1]["variant"]["status"] == "TIMEOUT"
    assert incomplete["seed_effects"]["505"]["n_pairs"] == 2
    with pytest.raises(ValueError, match="duplicate variant"):
        compare_groups([group], rows + rows[-1:], seeds, 3, stats)
