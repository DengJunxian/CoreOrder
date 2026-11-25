import gzip
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from jsonschema import Draft202012Validator, ValidationError

from coreorder.config import ROOT, json_bytes, sha256
from coreorder.contracts import CONTRACT_VERSION, INPUT_DTYPE, OUTPUT_DTYPE
from coreorder.schema import validate_record

FIXTURES = ROOT / "fixtures/pams"


def load_json(path):
    return json.loads(read_payload(path))


def read_payload(path):
    data = path.read_bytes()
    return gzip.decompress(data) if path.suffix == ".gz" else data


def rows(path):
    return [json.loads(line) for line in read_payload(path).splitlines()]


def test_native_record_layout():
    assert INPUT_DTYPE.itemsize == 112 and INPUT_DTYPE.alignment == 8
    assert OUTPUT_DTYPE.itemsize == 16 and OUTPUT_DTYPE.alignment == 8
    assert INPUT_DTYPE.isalignedstruct and INPUT_DTYPE.isnative
    assert OUTPUT_DTYPE.isalignedstruct and OUTPUT_DTYPE.isnative
    assert [field[1] for field in INPUT_DTYPE.fields.values()] == list(range(0, 104, 8)) + [104, 108]
    assert [field[1] for field in OUTPUT_DTYPE.fields.values()] == [0, 8, 12]
    assert [field[0] for field in INPUT_DTYPE.fields.values()] == [
        np.dtype("float64")
    ] * 10 + [np.dtype("int64")] * 3 + [np.dtype("int32")] * 2
    assert [field[0] for field in OUTPUT_DTYPE.fields.values()] == [
        np.dtype("float64"), np.dtype("int32"), np.dtype("int32")
    ]


def test_public_schemas():
    for path in (ROOT / "schemas").glob("*.schema.json"):
        Draft202012Validator.check_schema(load_json(path))
    config = {
        "backend": "py-seq", "book_restore": "upstream", "layout": "not_applicable",
        "workers": 1, "grain": None, "schedule": None, "seed": 42,
    }
    validate_record("run_config", config)
    for invalid in ({"workers": 0}, {"layout": "soa"}, {"grain": 32}):
        with pytest.raises(ValidationError):
            validate_record("run_config", config | invalid)
    validate_record("run_config", config | {
        "backend": "native-parallel", "layout": "soa", "workers": 4, "grain": 128, "schedule": "static",
    })


def test_fixture_provenance():
    manifest = load_json(FIXTURES / "manifest.json")
    lock = load_json(ROOT / "UPSTREAM.lock.json")
    assert manifest["contract_version"] == CONTRACT_VERSION == lock["contract_version"]
    assert manifest["pams_sha"] == next(d["sha"] for d in lock["dependencies"] if d["name"] == "PAMS")
    assert manifest["seed"] == 42
    assert manifest["generator_sha256"] == sha256((ROOT / "fixtures/generate.py").read_bytes())
    paths = {p.relative_to(FIXTURES).as_posix() for p in FIXTURES.rglob("*") if p.is_file()}
    assert paths == {"manifest.json", *manifest["files"]}
    for path, expected in manifest["files"].items():
        assert sha256((FIXTURES / path).read_bytes()) == expected


@pytest.mark.parametrize("label, n, steps", [("ci2002-smoke", 24, 80), ("event-state", 12, 24)])
def test_market_fixtures(label, n, steps):
    fixture = FIXTURES / label
    validate_record("workload", load_json(fixture / "config.json"))
    state = load_json(fixture / "final_state.json")
    validate_record("final_state", state)
    assert len(state["accounts"]) == n
    assert len(state["market_history"][0]["executed_volumes"]) == steps + 1
    validate_record("final_rng", load_json(fixture / "final_rng.json.gz"))

    trace = rows(fixture / "events.jsonl")
    assert [event["event_seq"] for event in trace] == list(range(len(trace)))
    for event in trace:
        validate_record("event", event)
    frames = rows(fixture / "market_steps.jsonl")
    states = rows(fixture / "step_states.jsonl.gz")
    assert len(frames) == len(states) == steps
    for frame, step_state in zip(frames, states, strict=True):
        validate_record("market_frame", frame)
        validate_record("step_state", step_state)
        assert step_state["step"] == frame["step"]
        assert len(step_state["accounts"]) == n
    if label == "event-state":
        assert any(event["event_kind"] == "expiration" for event in trace)
        assert float.fromhex(frames[9]["fundamental_price_hex"]) == 300.0
        assert float.fromhex(frames[10]["fundamental_price_hex"]) == 270.0
        assert load_json(fixture / "final_rng.json.gz")["events"]


def test_fcn_fixture_matches_abi_and_random_state():
    directory = FIXTURES / "fcn"
    decisions = rows(directory / "rows.jsonl")
    states = load_json(directory / "rng.json.gz")
    assert len(decisions) == len(states) == 24
    for mode, margin_type in (("fixed", 0), ("normal", 1)):
        validate_record("workload", load_json(directory / f"{mode}.json"))
        assert sum(row["input"]["margin_type"] == margin_type for row in decisions) == 12
    for row, state in zip(decisions, states, strict=True):
        validate_record("fcn_row", row)
        assert (state["workload"], state["call_index"]) == (row["workload"], row["call_index"])
        for phase in ("before", "after"):
            validate_record("python_rng", state[phase])
            assert sha256(json_bytes(state[phase])) == row[f"rng_{phase}_hash"]
        for dtype, key in ((INPUT_DTYPE, "input"), (OUTPUT_DTYPE, "output")):
            values = row[key]
            assert set(values) == set(dtype.names)
            native = np.array([tuple(
                float.fromhex(values[name]) if dtype[name].kind == "f" else values[name]
                for name in dtype.names
            )], dtype=dtype)
            assert native.flags.aligned and native.flags.c_contiguous


@pytest.mark.parametrize("suite", ["smoke", "g0"])
def test_missing_e1_is_blocked(tmp_path, suite):
    if (ROOT / "validation/e1.py").is_file():
        pytest.skip("the missing-E1 path requires a checkout without E1")
    out = tmp_path / suite
    invocation = subprocess.run(
        [sys.executable, "-m", "coreorder", "validate", "--suite", suite, "--output", str(out)],
        capture_output=True,
        text=True,
    )
    assert invocation.returncode == 3
    assert load_json(out / "status.json")["status"] == "BLOCKED"
    assert not (out / "e1").exists()
