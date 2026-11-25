import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

SMOKE = Path(__file__).resolve().parents[2] / "configs/workloads/smoke.json"


def invoke(output, *flags, module="coreorder", config=SMOKE):
    return subprocess.run(
        [sys.executable, "-m", module, *flags, "--config", str(config),
         "--seed", "42", "--output", str(output)],
        capture_output=True,
        text=True,
    )


def read(path):
    return json.loads(path.read_bytes())


def observations(directory, filename):
    rows = [json.loads(line) for line in (directory / filename).read_text().splitlines()]
    for row in rows:
        del row["run_id"]
    return rows


def test_py_seq_records_real_market_and_matches_upstream(tmp_path):
    reference = tmp_path / "reference"
    production = tmp_path / "production"
    result = invoke(reference, module="coreorder.reference")
    assert result.returncode == 0, result.stderr
    result = invoke(production, "run", "--backend", "py-seq", "--book-restore", "upstream")
    assert result.returncode == 0, result.stderr

    manifest = read(production / "manifest.json")
    assert (manifest["N"], manifest["M"], manifest["K"], manifest["steps"]) == (24, 1, 1, 80)
    assert manifest["backend_requested"] == manifest["backend_effective"] == "py-seq"
    assert manifest["input_hash"] == manifest["effective_config_hash"]
    assert (production / "effective_config.json").read_bytes() == SMOKE.read_bytes()

    metrics = read(production / "metrics.json")
    assert metrics["orders"] > 0 and metrics["executions"] > 0
    assert metrics["market_steps"] == 80
    for name in ("events.jsonl", "market_steps.jsonl"):
        assert observations(production, name) == observations(reference, name)
    for name in ("final_state.json", "final_rng.json"):
        assert (production / name).read_bytes() == (reference / name).read_bytes()

    final = read(production / "final_state.json")
    initial_accounts, accounts = final["initial_accounts"], final["accounts"]
    assert len(accounts) == 24 and accounts != initial_accounts
    assert sum(a["holdings"]["0"] for a in accounts) == sum(a["holdings"]["0"] for a in initial_accounts)
    assert math.isclose(
        math.fsum(float.fromhex(a["cash_hex"]) for a in initial_accounts),
        math.fsum(float.fromhex(a["cash_hex"]) for a in accounts),
        rel_tol=0.0, abs_tol=1e-7,
    )


@pytest.mark.parametrize("flags", [
    ("--backend", "py-thread"),
    ("--backend", "py-process"),
    ("--backend", "native-serial"),
    ("--backend", "native-parallel", "--layout", "soa", "--workers", "4", "--grain", "128", "--schedule", "static"),
    ("--book-restore", "incremental"),
])
def test_unimplemented_run_is_rejected_without_execution(tmp_path, flags):
    output = tmp_path / "unsupported"
    result = invoke(output, "run", *flags)
    assert result.returncode == 2
    assert "not implemented" in result.stderr
    assert read(output / "status.json")["status"] == "UNSUPPORTED"
    assert read(output / "manifest.json")["backend_effective"] is None
    assert not (output / "events.jsonl").exists()


def test_invalid_input_and_existing_run_directory(tmp_path):
    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]")
    output = tmp_path / "failed"
    result = invoke(output, "run", config=invalid)
    assert result.returncode == 1
    status = (output / "status.json").read_bytes()
    assert json.loads(status)["status"] == "FAIL"
    assert (output / "workload.json").read_bytes() == b"[]"

    result = invoke(output, "run")
    assert result.returncode != 0
    assert (output / "status.json").read_bytes() == status
