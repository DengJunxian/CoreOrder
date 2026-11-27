"""Run small production rejection, record-contract and fee-boundary probes."""

import copy
import sys
from collections import Counter
from pathlib import Path

from audit_p10 import execute
from validation.compare import compare
from validation.gate import evaluate_cell
from validation.io import read, write


def observe_rows(path):
    import json

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    for row in rows:
        del row["run_id"]
    return rows


def run(output):
    output.mkdir()
    result = {}
    settings = read("configs/workloads/smoke.json")
    settings["FCNAgents"]["numAgents"] = 1
    settings["simulation"]["sessions"] = [dict(
        settings["simulation"]["sessions"][0], iterationSteps=1,
    )]
    minimal = output / "one-step.json"
    write(minimal, settings)
    seed = 42

    def market_run(label, config, *options, module="coreorder", expected=0):
        target = output / label
        mode = ["run"] if module == "coreorder" else []
        code = execute(output / f"{label}-command", (
            "-m", module, *mode, "--config", config, "--seed", seed, "--output", target, *options,
        ))
        assert code == expected, (label, code)
        return target

    reference = output / "reference.json.gz"
    assert execute(output / "reference-command", (
        "-m", "validation", "collect", "--pams-root", "vendor/pams", "--config", minimal,
        "--seed", seed, "--output", reference,
    )) == 0
    original = read(reference)
    native = market_run("native", minimal, "--backend", "native-serial", "--validation-trace")
    trace = read(native / "validation-trace.json.gz")
    status = read(native / "status.json")
    manifest = read(native / "manifest.json")
    report = evaluate_cell(original, trace, manifest, status, {"backend_effective": "native-serial"})
    assert compare(original, trace)["status"] == "PASS"
    assert report["status"] == "FAIL" and report["field"] == "input_hash"
    result["minimal_record_failure"] = {
        "status": "FAIL", "seed": seed, "markets": 1, "agents": 1, "steps": 1,
        "first_location": "manifest.input_hash (before first event)",
        "manifest_raw_sha256": manifest["input_hash"],
        "reference_normalized_sha256": original["input_hash"], "E_result": report,
    }

    as_subclass = copy.deepcopy(settings)
    as_subclass["FCNAgents"]["class"] = "MarketShareFCNAgent"
    subclass = output / "unsupported-agent.json"
    write(subclass, as_subclass)
    for backend in ("native-serial", "native-parallel"):
        run_dir = market_run(f"reject-{backend}", subclass, "--backend", backend, expected=1)
        receipt = read(run_dir / "status.json")
        assert "requires exact PAMS FCNAgent" in receipt["reason"]
        assert read(run_dir / "manifest.json")["backend_effective"] == backend
        assert not (run_dir / "events.jsonl").read_bytes() and not (run_dir / "final_rng.json").exists()
        result[f"unsupported_{backend}"] = receipt["reason"]

    as_index = copy.deepcopy(settings)
    as_index["Market"]["outstandingShares"] = 100
    as_index["Index"] = {"class": "IndexMarket", "tickSize": 0.001,
                         "marketPrice": 300, "markets": ["Market"]}
    as_index["simulation"]["markets"].append("Index")
    index_config = output / "unsupported-market.json"
    write(index_config, as_index)
    run_dir = market_run("reject-index", index_config, "--backend", "native-parallel", expected=1)
    receipt = read(run_dir / "status.json")
    assert "requires exact PAMS Market" in receipt["reason"]
    assert not (run_dir / "events.jsonl").read_bytes()
    result["unsupported_index"] = receipt["reason"]

    fallback = output / "fallback"
    assert execute(output / "fallback-command", (
        "-m", "coreorder", "run", "--config", subclass, "--seed", seed, "--output", fallback,
        "--backend", "native-parallel", "--unsupported-policy", "upstream",
    )) == 2
    assert not fallback.exists()
    result["explicit_fallback"] = {
        "status": "NOT_RUN", "reason": "parser rejects --unsupported-policy upstream (exit 2)",
    }
    requested_py = market_run("manual-upstream", subclass, "--backend", "py-seq", "--validation-trace")
    known_subclass = output / "manual-upstream-reference.json.gz"
    assert execute(output / "manual-upstream-reference-command", (
        "-m", "validation", "collect", "--pams-root", "vendor/pams", "--config", subclass,
        "--seed", seed, "--output", known_subclass,
    )) == 0
    assert compare(read(known_subclass), read(requested_py / "validation-trace.json.gz"))["status"] == "PASS"
    assert read(requested_py / "manifest.json")["backend_effective"] == "py-seq"
    result["explicit_upstream_request"] = "PASS"

    failed = output / "missing-extension"
    assert execute(output / "missing-extension-command", (
        "-I", "-m", "coreorder", "run", "--backend", "native-parallel",
        "--config", minimal, "--seed", seed, "--output", failed,
    )) == 2
    assert read(failed / "status.json")["status"] == "UNSUPPORTED"
    assert read(failed / "manifest.json")["backend_effective"] is None
    result["missing_extension"] = "PASS"

    fee_settings = read("configs/workloads/native-serial-normal.json")
    fee_settings["MarketA"]["transactionFee"] = {"class": "ProportionalTransactionFee", "rate": 0.001}
    fee_config = output / "fee.json"
    write(fee_config, fee_settings)
    stock = market_run("fee-original-pams", fee_config, module="coreorder.reference")
    fee_candidate = market_run(
        "fee-native", fee_config, "--backend", "native-parallel", "--layout", "soa",
        "--workers", "4", "--book-restore", "incremental",
    )
    for log in ("events.jsonl", "market_steps.jsonl", "step_states.jsonl"):
        assert observe_rows(stock / log) == observe_rows(fee_candidate / log), log
    for record in ("final_state.json", "final_rng.json"):
        assert (stock / record).read_bytes() == (fee_candidate / record).read_bytes(), record
    executions = [row for row in observe_rows(stock / "events.jsonl") if row["event_kind"] == "execution"]
    assert executions and any(float.fromhex(row["buy_transaction_fee_hex"]) > 0 for row in executions)
    fee_reference = output / "fee-E-reference.json.gz"
    code = execute(output / "fee-E-command", (
        "-m", "validation", "collect", "--pams-root", "vendor/pams", "--config", fee_config,
        "--seed", seed, "--output", fee_reference,
    ))
    assert code == 1
    error = (output / "fee-E-command/stderr.log").read_text().splitlines()[-1]
    result["fee"] = {"production_differential": "PASS", "executions": len(executions),
                     "E_full_trace": "BLOCKED", "reason": error}
    write(output / "summary.json", result)
    for name, value in result.items():
        print(name, value)


if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve())
