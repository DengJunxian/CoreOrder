import json
import pstats
import subprocess
import sys
from pathlib import Path

import pytest

from coreorder.cli import main
from coreorder.measurement import pmu_receipt
from coreorder.schema import validate_record

from test_py_seq import invoke, read

WORKLOAD = Path(__file__).resolve().parents[2] / "configs/workloads/native-serial-normal.json"
BACKENDS = [
    ("py-seq", 1, None), ("py-thread", 2, None), ("py-process", 2, None),
    ("native-serial", 1, "aos"), ("native-serial", 1, "soa"),
    ("native-parallel", 2, "aos"), ("native-parallel", 2, "soa"),
]
PHASES = ("draw_pack_s", "native_compute_s", "rebuild_orders_s", "handle_orders_s", "optional_restore_s")


def run_mode(output, mode, *flags):
    result = invoke(output, "run", "--mode", mode, *flags, config=WORKLOAD)
    assert result.returncode == 0, result.stderr
    records = {name: read(output / f"{name}.json") for name in
               ("manifest", "environment", "status", "metrics", "final_state", "final_rng")}
    for name, record in records.items():
        validate_record(name, record)
    return records


@pytest.mark.parametrize("restore", ["upstream", "incremental"])
@pytest.mark.parametrize("backend,workers,layout", BACKENDS)
def test_validation_timing_equivalence(tmp_path, restore, backend, workers, layout):
    flags = ["--backend", backend, "--workers", str(workers), "--book-restore", restore]
    if layout:
        flags.extend(("--layout", layout))
    if backend == "native-parallel":
        flags.extend(("--schedule", "dynamic", "--grain", "1"))
    validation_dir, timing_dir = tmp_path / "validation", tmp_path / "timing"
    validation = run_mode(validation_dir, "validation", *flags)
    timing = run_mode(timing_dir, "timing", *flags)
    assert validation["status"]["validation_status"] == "PASS"
    assert read(validation_dir / "comparison.json")["status"] == "PASS"
    assert timing["status"]["validation_status"] == "NOT_RUN"
    assert {path.name for path in validation_dir.glob("*.jsonl")} == {
        "events.jsonl", "market_steps.jsonl", "step_states.jsonl",
    }
    assert not list(timing_dir.glob("*.jsonl"))
    for name in ("validation-trace.json.gz", "process_copy.json", "heap_diagnostics.json",
                 "profile.prof", "phases.json"):
        assert not (timing_dir / name).exists()
    for key in ("backend_effective", "book_restore", "workers", "grain", "schedule", "layout",
                "runner_class", "python_executor_class", "process_start_method", "native_binding",
                "input_hash", "effective_config_hash"):
        assert timing["manifest"].get(key) == validation["manifest"].get(key), key
    assert timing["manifest"]["backend_effective"] == backend
    assert timing["environment"]["native_module"] == validation["environment"]["native_module"]
    for key in ("final_state", "final_rng"):
        assert timing[key] == validation[key]
        assert (timing_dir / f"{key}.json").read_bytes() == (validation_dir / f"{key}.json").read_bytes()
    for key in ("final_state_hash", "rng_hash"):
        assert timing["status"][key] == validation["status"][key]
    assert "trace_hash" not in timing["status"]
    assert "trace_hash" in validation["status"]
    metrics = timing["metrics"]
    for key in ("orders", "cancels", "expirations", "executions", "market_steps", "native_rows",
                "agent_calls", "decision_rows", "gauss_api_calls", "native_executor_creations"):
        assert metrics.get(key) == validation["metrics"].get(key), key
    assert metrics["orders"] > 0 and metrics["executions"] > 0 and metrics["expirations"] > 0
    assert metrics["market_steps"] == 18
    assert metrics["setup_s"] > 0 and metrics["simulation_s"] > 0
    assert metrics["process_wall_s"] > metrics["setup_s"] + metrics["simulation_s"]
    assert metrics["process_wall_s"] == read(timing_dir / "launch/command.json")["elapsed_s_driver"]
    assert metrics["metric_sources"]["process_wall_s"] == "measured"
    assert metrics["batch_widths"] is None
    assert all(metrics[key] is None and metrics["unmeasured"][key] for key in PHASES)
    if layout:
        assert metrics["native_rows"] > 0
        assert metrics["native_executor_creations"] == int(backend == "native-parallel")
    if backend == "py-process":
        assert read(validation_dir / "process_copy.json")["serialized_dispatch_bytes"] > 0
        assert timing["manifest"]["process_start_method"] == "spawn"


@pytest.mark.parametrize("layout,restore", [("aos", "upstream"), ("soa", "incremental")])
def test_profile_observes_shared_native_phases(tmp_path, layout, restore):
    flags = ("--backend", "native-parallel", "--workers", "2", "--layout", layout, "--book-restore", restore)
    timing = run_mode(tmp_path / "timing", "timing", *flags)
    profile = run_mode(tmp_path / "profile", "profile", *flags)
    spans = read(tmp_path / "profile/phases.json")
    assert all(profile["metrics"][key] > 0 for key in PHASES)
    assert spans["calls"]["draw_pack_s"] == spans["calls"]["native_compute_s"] == spans["calls"]["rebuild_orders_s"]
    assert spans["calls"]["account_updates"] > 0
    assert profile["final_state"] == timing["final_state"]
    assert profile["final_rng"] == timing["final_rng"]


def test_function_profile(tmp_path):
    output = tmp_path / "function-profile"
    records = run_mode(output, "profile", "--cprofile")
    assert any(name[2] == "_handle_orders" for name in pstats.Stats(str(output / "profile.prof")).stats)
    assert all(records["metrics"][key] is None for key in PHASES)


def test_timing_keeps_snapshot_and_profiling_outside_simulation(tmp_path, monkeypatch):
    from pams.runners import SequentialRunner
    from coreorder import run_records, snapshot

    # Pytest puts the source checkout on sys.path. Capture the CLI's actual installed environment.
    installed = json.loads(subprocess.check_output([
        sys.executable, "-c", "import json; from coreorder.environment import environment; print(json.dumps(environment()))",
    ]))
    monkeypatch.setattr(run_records, "environment", lambda: installed)

    active = False
    original = SequentialRunner._run

    def run(runner):
        nonlocal active
        assert isinstance(runner.logger, snapshot.WorkloadCounts)
        assert sys.getprofile() is None
        active = True
        try:
            return original(runner)
        finally:
            active = False

    monkeypatch.setattr(SequentialRunner, "_run", run)
    observed = []
    for module, name in ((run_records, "final_state"), (run_records, "final_rng"), (snapshot, "accounts"),
                         (snapshot, "ordered_book"), (snapshot, "market_state")):
        def guard(*args, original=getattr(module, name), name=name, **kwargs):
            assert not active, name
            observed.append(name)
            return original(*args, **kwargs)
        monkeypatch.setattr(module, name, guard)
    output = tmp_path / "timing"
    output.mkdir()
    assert main(["run", "--mode", "timing", "--_measurement-child", "--config", str(WORKLOAD),
                 "--seed", "42", "--output", str(output)]) == 0
    assert observed.count("final_state") == observed.count("final_rng") == observed.count("accounts") == 1
    assert observed.count("ordered_book") == 4


def test_mode_rejects_diagnostic_flags(tmp_path):
    result = invoke(tmp_path / "run", "run", "--mode", "timing", "--count-heap-comparisons")
    assert result.returncode == 2
    assert not (tmp_path / "run").exists()


def test_perf_receipt_preserves_unavailable_counts(tmp_path):
    raw = tmp_path / "perf-stat.csv"
    raw.write_text("# header\n124;;cycles;300;100.00;;\n<not supported>;;instructions;0;0.00;;\n")
    result = pmu_receipt(raw, ["cycles", "instructions"], {"status": "PASS"})
    assert result["status"] == "FAIL"
    assert [item["count"] for item in result["rows"]] == [124, None]
    assert json.loads(json.dumps(result)) == result
