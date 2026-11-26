"""A-side paired runs using the unmodified PAMS runner as reference."""

import itertools
import json
import math
import statistics
import subprocess
import sys

import pytest

from coreorder.config import ROOT, json_bytes, sha256
from coreorder.schema import validate_record

SMOKE = ROOT / "fixtures/pams/ci2002-smoke/config.json"
EVENT_STATE = ROOT / "fixtures/pams/event-state/config.json"
CI2002 = ROOT / "vendor/pams/samples/CI2002/config.json"
C01_SEEDS = (101, 202, 303, 404, 505)
STREAMS = ("events.jsonl", "market_steps.jsonl", "step_states.jsonl")
FINALS = ("final_state.json", "final_rng.json")


def read(path):
    return json.loads(path.read_bytes())


def invoke(config, seed, output, *flags, reference=False, expected=0):
    entry = ("coreorder.reference",) if reference else ("coreorder", "run")
    command = [sys.executable, "-m", *entry, "--config", str(config), "--seed", str(seed),
               "--output", str(output), *flags]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == expected, (command, result.stdout, result.stderr, output)


def observations(directory, filename):
    if filename in FINALS:
        return [read(directory / filename)]
    with (directory / filename).open() as stream:
        rows = [json.loads(line) for line in stream]
    for row in rows:
        del row["run_id"]
    return rows


def differing_path(a, b, path=()):
    if type(a) is type(b) and isinstance(a, dict) and a.keys() == b.keys():
        for key in a:
            if a[key] != b[key]:
                return differing_path(a[key], b[key], (*path, key))
    if type(a) is type(b) and isinstance(a, list) and len(a) == len(b):
        for index, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return differing_path(x, y, (*path, index))
    return list(path)


def compare_runs(reference, candidate, config, seed):
    for filename in (*STREAMS, *FINALS):
        a, b = (observations(directory, filename) for directory in (reference, candidate))
        for i, (x, y) in enumerate(itertools.zip_longest(a, b)):
            if x != y:
                report = candidate.parent / "first_divergence.json"
                context = slice(max(0, i - 1), i + 2)
                report.write_bytes(json_bytes({
                    "artifact": filename, "row": i, "field": differing_path(x, y),
                    "reference": a[context], "candidate": b[context], "seed": seed,
                    "workload": str(config),
                    "reference_states": str(reference / "step_states.jsonl"),
                    "candidate_states": str(candidate / "step_states.jsonl"),
                    "reference_rng": str(reference / "final_rng.json"),
                    "candidate_rng": str(candidate / "final_rng.json"),
                }))
                pytest.fail(f"{filename} differs at row {i}: {report}")


def paired_run(config, seed, tmp_path):
    reference = tmp_path / "reference"
    candidate = tmp_path / "incremental"
    invoke(config, seed, reference, reference=True)
    invoke(config, seed, candidate, "--book-restore", "incremental")
    compare_runs(reference, candidate, config, seed)
    assert (candidate / "workload.json").read_bytes() == config.read_bytes()
    manifest = read(candidate / "manifest.json")
    validate_record("manifest", manifest)
    assert manifest["book_restore"] == "incremental"
    assert manifest["backend_requested"] == manifest["backend_effective"] == "py-seq"
    assert not (candidate / "heap_diagnostics.json").exists()
    effective = (candidate / "effective_config.json").read_bytes()
    assert manifest["effective_config_hash"] == sha256(effective)
    assert manifest["input_hash"] == sha256(config.read_bytes())
    original = read(config)
    for name in original["simulation"]["markets"]:
        original[name]["class"] = "CoreOrderMarket"
    assert json.loads(effective) == original
    metrics, status = (read(candidate / f"{name}.json") for name in ("metrics", "status"))
    print(
        f"{config.stem} seed={seed}: events/step/final/RNG equal; "
        f"steps={metrics['market_steps']} orders={metrics['orders']} "
        f"fills={metrics['executions']} expirations={metrics['expirations']} "
        f"trace_sha256={status['trace_hash']}"
    )


@pytest.mark.parametrize("seed", (42, 20261125))
@pytest.mark.parametrize("margin", ("fixed", "normal"))
@pytest.mark.parametrize("window", ((3, 6), (100, 200)), ids=("short", "long"))
def test_probe_full_simulations(tmp_path, seed, margin, window):
    workload = read(CI2002)
    workload["FCNAgents"].update(numAgents=64, marginType=margin, timeWindowSize=list(window))
    for index, session in enumerate(workload["simulation"]["sessions"]):
        session.update(iterationSteps=10 if index == 0 else 50, maxNormalOrders=16, withPrint=False)
    config = tmp_path / f"ci2002-probe-{margin}-{window[0]}-{window[1]}.json"
    config.write_bytes(json_bytes(workload))
    paired_run(config, seed, tmp_path)


@pytest.mark.parametrize("seed", C01_SEEDS)
@pytest.mark.parametrize("config", (SMOKE, EVENT_STATE), ids=("ci2002-smoke", "event-state"))
def test_c01_serial_representatives(tmp_path, config, seed):
    paired_run(config, seed, tmp_path)


def test_heap_diagnostic_switches(tmp_path):
    config = tmp_path / "inherited-market.json"
    workload = read(SMOKE)
    workload["Template"] = workload.pop("Market")
    workload["Market"] = {"extends": "Template"}
    config.write_text(json.dumps(workload), encoding="utf-8")

    reports = {}
    for mode in ("upstream", "incremental"):
        output = tmp_path / mode
        invoke(config, 42, output, "--book-restore", mode, "--heap-diagnostics", "--count-heap-comparisons")
        reports[mode] = read(output / "heap_diagnostics.json")
    compare_runs(tmp_path / "upstream", tmp_path / "incremental", config, 42)
    effective = read(tmp_path / "incremental/effective_config.json")
    assert list(effective) == list(workload)
    assert effective["Market"] == {
        "extends": "Template", "class": "CoreOrderMarket",
    }
    upstream, incremental = reports["upstream"], reports["incremental"]
    restore_calls = upstream["restore_calls"]
    assert restore_calls == incremental["restore_calls"] > 0
    total_k = 0
    for side in ("buy", "sell"):
        assert upstream[side] == incremental[side]
        assert incremental[side]["restore_calls"] == restore_calls
        rows = incremental[side]["rows"]
        for row in rows:
            n, h, k = (row[f] for f in ("heap_length_before", "heap_length_remaining", "popped_count"))
            assert n == h + k
            assert row["restore_fraction"] == k / max(n, 1)
        total_k += sum(row["popped_count"] for row in rows)
        ratios = sorted(row["restore_fraction"] for row in rows)
        n_sum, h_sum, k_sum = [
            sum(row[key] for row in rows)
            for key in ("heap_length_before", "heap_length_remaining", "popped_count")
        ]
        print(f"diagnostics {side}: calls={restore_calls} sum(n,h,k)={(n_sum, h_sum, k_sum)} "
              f"k/max(n,1) min/p50/p90/max="
              f"{(ratios[0], statistics.median(ratios), ratios[math.ceil(len(ratios) * 0.9) - 1], ratios[-1])}")
    assert upstream["heapq_calls"] == {"heapify": 2 * restore_calls, "heappush": 0}
    assert incremental["heapq_calls"] == {"heapify": 0, "heappush": total_k}
    for mode, report in reports.items():
        assert all(value > 0 for value in report["restore_order_lt_calls"].values())
        print(f"diagnostics {mode}: {report['heapq_calls']}; Order.__lt__ {report['restore_order_lt_calls']}")

    one_flag = (
        ("upstream", "--count-heap-comparisons", {"restore_order_lt_calls": upstream["restore_order_lt_calls"]}),
        ("incremental", "--heap-diagnostics", {key: value for key, value in incremental.items()
                                               if key != "restore_order_lt_calls"}),
    )
    for mode, flag, expected in one_flag:
        output = tmp_path / f"{mode}-single-flag"
        invoke(config, 42, output, "--book-restore", mode, flag)
        assert read(output / "heap_diagnostics.json") == expected
        compare_runs(tmp_path / mode, output, config, 42)


def test_incremental_rejects_unsupported_market(tmp_path):
    config = tmp_path / "index_market.json"
    workload = read(SMOKE)
    workload["Market"]["class"] = "IndexMarket"
    config.write_bytes(json_bytes(workload))
    output = tmp_path / "unsupported"
    invoke(config, 42, output, "--book-restore", "incremental", expected=2)
    status = read(output / "status.json")
    assert status["status"] == "UNSUPPORTED"
    assert "requires PAMS Market" in status["reason"]
    assert read(output / "manifest.json")["backend_effective"] is None


def test_first_difference_keeps_order_and_rng_references(tmp_path):
    reference, candidate = tmp_path / "reference", tmp_path / "candidate"
    reference.mkdir()
    candidate.mkdir()
    (reference / "events.jsonl").write_bytes(
        json_bytes({"run_id": "left", "order_id": 1}) + json_bytes({"run_id": "left", "order_id": 2})
    )
    (candidate / "events.jsonl").write_bytes(
        json_bytes({"run_id": "right", "order_id": 2}) + json_bytes({"run_id": "right", "order_id": 1})
    )
    with pytest.raises(pytest.fail.Exception, match="events.jsonl differs at row 0"):
        compare_runs(reference, candidate, SMOKE, 42)
    report = read(tmp_path / "first_divergence.json")
    assert report["field"] == ["order_id"]
    assert report["reference"] == [{"order_id": 1}, {"order_id": 2}]
    assert report["candidate"] == [{"order_id": 2}, {"order_id": 1}]
    assert report["reference_rng"] == str(reference / "final_rng.json")
    assert report["candidate_rng"] == str(candidate / "final_rng.json")
