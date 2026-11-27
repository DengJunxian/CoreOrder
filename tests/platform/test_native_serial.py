"""P07 production direct-serial checks. Numerical success always uses Member B's extension."""

import json
import subprocess
import sys
from collections import defaultdict
from importlib.util import find_spec

import pytest

from coreorder.schema import validate_record
from test_py_seq import SMOKE, invoke, observations, read

NORMAL = SMOKE.with_name("native-serial-normal.json")
requires_native = pytest.mark.skipif(
    find_spec("_coreorder_fcn") is None, reason="build _coreorder_fcn and add its directory to PYTHONPATH",
)


@requires_native
@pytest.mark.parametrize("config", [SMOKE, NORMAL])
def test_native_serial_matches_py_seq(tmp_path, config):
    reference = tmp_path / "reference"
    candidate = tmp_path / "native"
    for output, backend in ((reference, "py-seq"), (candidate, "native-serial")):
        result = invoke(output, "run", "--backend", backend, "--book-restore", "upstream", config=config)
        assert result.returncode == 0, result.stderr
    for name in ("events.jsonl", "market_steps.jsonl", "step_states.jsonl"):
        assert observations(candidate, name) == observations(reference, name)
    for name in ("final_state.json", "final_rng.json"):
        assert (candidate / name).read_bytes() == (reference / name).read_bytes()
    assert (candidate / "workload.json").read_bytes() == (candidate / "effective_config.json").read_bytes()
    assert (candidate / "workload.json").read_bytes() == config.read_bytes()

    records = {name: read(candidate / f"{name}.json") for name in ("manifest", "metrics", "status", "environment")}
    for name, data in records.items():
        validate_record(name, data)
    manifest, metrics = records["manifest"], records["metrics"]
    assert manifest["backend_requested"] == manifest["backend_effective"] == "native-serial"
    assert manifest["layout"] == "aos" and manifest["workers"] == 1
    assert records["environment"]["native_module"]["contract_version"] == "coreorder-r4-v1"
    assert metrics["decision_rows"] == metrics["native_rows"] > 0
    assert metrics["agent_calls"] == sum(metrics["batch_widths"])

    if config == SMOKE:
        assert set(metrics["batch_widths"]) == {1}
        assert metrics["gauss_api_calls"] == metrics["native_rows"]
    else:
        assert metrics["gauss_api_calls"] == 2 * metrics["native_rows"]
        assert 1 in metrics["batch_widths"] and max(metrics["batch_widths"]) == 3
        assert metrics["agent_calls"] > 8 * 3
        orders = [row for row in observations(candidate, "events.jsonl") if row["event_kind"] == "order"]
        regular = defaultdict(list)
        for row in orders:
            if row["agent_id"] < 12:
                regular[row["step"]].append(row["agent_id"])
        assert 0 not in regular
        assert all(len(set(ids)) <= 3 for ids in regular.values())
        assert any(len(ids) > 3 for ids in regular.values())
        assert any(row["agent_id"] == 12 for row in orders)


@requires_native
@pytest.mark.parametrize("problem", ["subclass", "zero_weights"])
def test_native_failure_stops_run_without_fallback(tmp_path, problem):
    config = read(SMOKE)
    if problem == "subclass":
        config["FCNAgents"]["class"] = "MarketShareFCNAgent"
        message = "requires exact PAMS FCNAgent"
    else:
        config["FCNAgents"].update(fundamentalWeight=0.0, chartWeight=0.0, noiseWeight=0.0)
        message = "FCN row 0 failed"
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(config))
    output = tmp_path / "run"
    result = invoke(output, "run", "--backend", "native-serial", config=source)
    assert result.returncode == 1, result.stderr
    assert message in read(output / "status.json")["reason"]
    assert read(output / "status.json")["status"] == "FAIL"
    assert read(output / "manifest.json")["backend_effective"] == "native-serial"
    assert (output / "events.jsonl").read_bytes() == b""
    assert not (output / "final_rng.json").exists()


def test_native_serial_requires_a_built_extension(tmp_path):
    result = subprocess.run(
        [sys.executable, "-I", "-m", "coreorder", "run", "--backend", "native-serial", "--config", str(SMOKE),
         "--seed", "42", "--output", str(tmp_path / "run")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2, result.stderr
    assert "_coreorder_fcn" in result.stderr
    output = tmp_path / "run"
    assert read(output / "status.json")["status"] == "UNSUPPORTED"
    assert read(output / "manifest.json")["backend_effective"] is None
    assert not (output / "events.jsonl").exists()


@requires_native
@pytest.mark.parametrize("backend,workers", [("native-serial", 1), ("native-parallel", 4)])
@pytest.mark.parametrize("layout", ["aos", "soa"])
@pytest.mark.parametrize("invalid_prefix", [False, True])
def test_packing_failure_preserves_first_invalid_row(tmp_path, backend, workers, layout, invalid_prefix):
    regression = SMOKE.parents[2] / "docs/gates/evidence/p08-first-failure.json"
    settings = read(regression)
    if not invalid_prefix:
        settings["ZeroWeight"]["fundamentalWeight"] = 1
    source = tmp_path / "mixed-invalid.json"
    source.write_text(json.dumps(settings, allow_nan=False))
    output = tmp_path / "run"
    result = subprocess.run(
        [sys.executable, "-m", "coreorder", "run", "--backend", backend, "--workers", str(workers),
         "--layout", layout, "--book-restore", "incremental", "--seed", "3",
         "--config", str(source), "--output", str(output)],
        capture_output=True, text=True, timeout=30,
    )
    message = "FCN row 0 failed with error 1" if invalid_prefix else "row 1 (1, 0): non-finite numeric field"
    assert result.returncode == 1 and message in result.stderr
    assert read(output / "status.json")["status"] == "FAIL"
    assert read(output / "manifest.json")["backend_effective"] == backend
    assert not (output / "final_rng.json").exists()
    assert (output / "events.jsonl").read_bytes() == b""
