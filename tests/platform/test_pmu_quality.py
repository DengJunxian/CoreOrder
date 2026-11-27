"""Synthetic fixtures for formal PMU data admission. No hardware values are inferred."""

from types import SimpleNamespace

import pytest

from analysis.pmu import WORK_FIELDS, check_capture, locked_quality
from analysis.report import observations
from coreorder.measurement import pmu_receipt
from experiments.protocol import condition, file_hash
from validation.io import write


EVENTS = ["branches:u", "branch-misses:u"]
KERNEL = "6.18.33.2-microsoft-standard-WSL2"


def capture(directory, csv, events=EVENTS):
    raw = directory / "perf-stat.csv"
    raw.write_text(csv)
    tool = directory / "test-perf"
    tool.write_text("synthetic binary identity")
    launch = {"command": [str(tool), "stat", "--no-big-num", "--no-scale", "-x", ";", "-o", str(raw),
                          *[arg for event in events for arg in ("-e", event)], "--",
                          "/venv/bin/python", "-m", "coreorder", "run", "--mode", "pmu", "--_measurement-child"],
              "status": "PASS", "exit_code": 0, "dirty": False, "git_sha": "test-source"}
    return raw, pmu_receipt(raw, events, launch), launch, file_hash(tool)


@pytest.mark.parametrize(("second", "reason"), [
    ("0;;branch-misses:u;100000;5.00;;\n", "low_running_coverage:branch-misses:u"),
    ("0;;branch-misses:u;0;100.00;;\n", "invalid_running_time:branch-misses:u"),
    ("0;;branch-misses;100000;100.00;;\n", "wrong_event:branch-misses:u"),
    ("", "missing_event"),
    ("<not supported>;;branch-misses:u;0;100.00;;\n", "not_supported:branch-misses:u"),
    ("<not counted>;;branch-misses:u;0;100.00;;\n", "not_counted:branch-misses:u"),
    ("-1;;branch-misses:u;100000;100.00;;\n", "invalid_count:branch-misses:u"),
    ("NaN;;branch-misses:u;100000;100.00;;\n", "invalid_count:branch-misses:u"),
    ("18446744073709551616;;branch-misses:u;100000;100.00;;\n", "invalid_count:branch-misses:u"),
    ("0;;branch-misses:u;100000;101.00;;\n", "invalid_running_coverage:branch-misses:u"),
    ("0;;branch-misses:u;100000;NaN;;\n", "invalid_running_coverage:branch-misses:u"),
    ("0;;branch-misses:u;100000;94.99;;\n", "low_running_coverage:branch-misses:u"),
    ("0;;branch-misses:u;100000;95.00;;\n", None),
    ("0;;branch-misses:u;100000;99.00;;\n", None),
    ("0;;branch-misses:u;100000;100.00;;\n", None),
    ("1;;branches:u;100000;100.00;;\n0;;branch-misses:u;100000;100.00;;\n", "extra_or_duplicate_event"),
])
def test_perf_counts_and_coverage(tmp_path, second, reason):
    raw, receipt, launch, sha = capture(tmp_path, "100;;branches:u;100000;100.00;;\n" + second)
    before = raw.read_bytes()
    quality = check_capture(raw, receipt, launch, EVENTS, sha)
    if reason:
        assert quality["status"] == "INELIGIBLE"
        assert reason in quality["reasons"]
    else:
        assert quality["status"] == "QUALIFIED"
        assert receipt["rows"][1]["count"] == 0
        assert quality["coverage"][1]["multiplexed"] == ("100.00" not in second)
    if ";0;100.00;" in second:
        assert quality["coverage"][1]["multiplexed"] is None
    if ";5.00;" in second:
        assert receipt["status"] == "PASS"
    assert raw.read_bytes() == before


def test_perf_scope_nonzero_exit_and_aliases(tmp_path):
    events = ["L1-dcache-loads:u", "L1-dcache-load-misses:u"]
    raw, receipt, launch, sha = capture(tmp_path, "10;;L1-dcache-loads;1000;100.00;;\n"
                                        "1;;L1-dcache-load-misses;1000;100.00;;\n", events)
    assert check_capture(raw, receipt, launch, events, sha)["status"] == "QUALIFIED"
    assert "wrong_perf_executable" in check_capture(raw, receipt, launch, events, "a" * 64)["reasons"]
    assert "perf_nonzero_exit" in check_capture(raw, receipt, {**launch, "exit_code": 1}, events, sha)["reasons"]
    launch["command"].remove("--no-scale")
    assert "wrong_perf_command_or_scope" in check_capture(raw, receipt, launch, events, sha)["reasons"]


def report_fixture(tmp_path, coverage):
    core = tmp_path / "attempt/core"
    core.mkdir(parents=True)
    (core / "launch").mkdir()
    _, counters, launch, tool_sha = capture(core, f"100;;branches:u;100000;{coverage};;\n"
                                           f"0;;branch-misses:u;100000;{coverage};;\n")
    write(core / "pmu.json", counters)
    write(core / "launch/command.json", launch)
    runtime = {"host_id": "test-host", "git_sha": launch["git_sha"]}
    write(core / "environment.json", {**runtime, "kernel": KERNEL, "architecture": "x86_64", "dirty": False})
    v01_root = tmp_path / "validation"
    v01 = v01_root / "raw/pams-v01/v01-run"
    v01.mkdir(parents=True)
    work = dict.fromkeys(WORK_FIELDS, 1)
    write(v01 / "validation-receipt.json", {"fixture": "synthetic"})
    write(v01 / "record.json", {"metrics": work})
    seal = {name: file_hash(v01 / name) for name in ("validation-receipt.json", "record.json")}
    write(v01 / "seal.json", {"files_sha256": seal})
    binding = {"case_id": "pams-v01", "run_id": "v01-run", "sha256": seal["validation-receipt.json"]}
    row = {"id": "test-row", "phase": "E05-PMU", "workload": "test", "seed": 101, "settings": {
           "backend": "py-seq", "book_restore": "upstream", "layout": "not_applicable", "workers": 1},
           "events": EVENTS, "event_group": "branch"}
    workload = {"input_sha256": "test-input", "canonical_input_hash": "test-canonical",
                "effective_sha256": {"upstream": "test-input"}}
    protocol = SimpleNamespace(lock={"PMU_quality": locked_quality(tool_sha, KERNEL),
                                     "primary_x86": {"actual_pmu_events": {"branch": EVENTS}}},
                               plan={"diagnostics": {"PMU_enabled": True}}, workloads={"test": workload})
    terminal = {"final_state_hash": "test-final", "rng_hash": "test-rng"}
    permit = {"identity": condition(workload, row, runtime), "reference_run_id": "oracle", "production_final": terminal}
    external = {"pams-v01": (permit, {"run_id": binding["run_id"], "sha256": binding["sha256"]})}
    record = {"status": {"status": "PASS", "validation_status": "PASS", "reference_run_id": "oracle",
                         "censoring": None, "reason": None, **terminal},
              "manifest": {"backend_effective": "py-seq", "validation_run_id": "v01-run",
                           "run_id": "pmu-run", "scope": "formal-diagnostic", **runtime},
              "metrics": {**work, "pmu": counters}, "validation": binding}
    attempts = {"test-row": {"directory": core.parent, "record": record, "files_sha256": {"record.json": "test-sha"}}}
    return protocol, [row], attempts, runtime, external, v01_root


@pytest.mark.parametrize(("coverage", "defect", "reason"), [
    ("5.00", None, "low_running_coverage:branches:u"),
    ("95.00", None, None),
    ("100.00", "workload", "v01_financial_workload_differs"),
    ("100.00", "policy", "missing_or_different_frozen_pmu_policy"),
    ("100.00", "kernel", "wrong_pmu_host_or_source"),
    ("100.00", "receipt_mismatch", "pmu_receipt_differs_from_sealed_metrics"),
    ("100.00", "v01_record_tamper", "v01_workload_evidence_differs"),
])
def test_formal_report_keeps_attempt_but_excludes_ineligible_counters(tmp_path, coverage, defect, reason):
    args = report_fixture(tmp_path, coverage)
    protocol, _, attempts, _, _, receipts = args
    attempt = attempts["test-row"]
    if defect == "workload":
        attempt["record"]["metrics"]["orders"] = 42
    elif defect == "policy":
        del protocol.lock["PMU_quality"]
    elif defect == "kernel":
        environment = attempt["directory"] / "core/environment.json"
        environment.unlink()
        write(environment,
              {"kernel": "different", "host_id": "test-host", "git_sha": "test-source",
               "architecture": "x86_64", "dirty": False})
    elif defect == "receipt_mismatch":
        attempt["record"]["metrics"]["pmu"]["rows"][0]["count"] = 50
    elif defect == "v01_record_tamper":
        (receipts / "raw/pams-v01/v01-run/record.json").write_text("{}")
    [reported] = observations(*args)
    assert reported["status"] == "PASS"
    if reason:
        assert "pmu" not in reported and reported["pmu_quality"]["status"] == "INELIGIBLE"
        assert reason in reported["pmu_quality"]["reasons"]
    else:
        assert reported["pmu_quality"]["status"] == "QUALIFIED"
        assert reported["pmu"]["rows"][1]["count"] == 0


def test_formal_pmu_figures_use_only_qualified_rows(tmp_path):
    pytest.importorskip("matplotlib")
    from analysis.figures import render_figures
    from experiments.protocol import DEFAULT
    from validation.io import read

    args = report_fixture(tmp_path, "5.00")
    [row] = observations(*args)
    # Even a legacy PMU count payload must not rescue an ineligible row.
    row["pmu"] = args[2]["test-row"]["record"]["metrics"]["pmu"]
    specification = read(DEFAULT / "figures.json")["figures"]
    write(tmp_path / "report.json", {})
    render_figures({"scope": "formal-diagnostic", "rows": [row], "additional_sources": [], "comparisons": []},
                   specification, tmp_path)
    figures = tmp_path / "figures"
    assert read(figures / "lineage.json")["figures"]["F5-pmu"]["status"] == "MISSING"
    assert not list(figures.glob("F5-pmu-*.pdf"))



def test_unstarted_pmu_is_distinct_from_invalid_pmu(tmp_path):
    args = report_fixture(tmp_path, "100.00")
    record = args[2]["test-row"]["record"]
    record["status"]["status"] = "NOT_RUN"
    [reported] = observations(*args)
    assert reported["status"] == "NOT_RUN" and "pmu_quality" not in reported and "pmu" not in reported
