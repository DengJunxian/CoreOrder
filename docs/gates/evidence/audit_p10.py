"""Read-only P10 acceptance of the frozen production candidate."""

import copy
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

from validation.cases import cases as member_e_cases
from validation.compare import compare, save_reproducer
from validation.gate import evaluate_cell
from validation.invariants import check
from validation.io import read, write
from validation.records import validate_record as member_e_records
from validation.upstream import load

ROOT = Path.cwd()
PAMS = ROOT / "vendor/pams"
INPUT_SHA = "92f8bbf08da514dcb24e27b6a815d3947c352798"


def execute(directory, args, timeout=45):
    command = [sys.executable, "-B", *map(str, args)]
    directory.mkdir()
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=timeout)
        info = {"argv": command, "cwd": str(ROOT), "exit": result.returncode}
        stdout, stderr = result.stdout, result.stderr
    except subprocess.TimeoutExpired as error:
        info = {"argv": command, "cwd": str(ROOT), "exit": None, "status": "TIMEOUT", "timeout_s": timeout}
        stdout, stderr = error.stdout or b"", error.stderr or b""
    write(directory / "command.json", info)
    (directory / "stdout.log").write_bytes(stdout)
    (directory / "stderr.log").write_bytes(stderr)
    return info["exit"]


def reference(config, seed, directory):
    load(PAMS)
    from pams.agents.base import Agent
    from pams.agents.fcn_agent import FCNAgent
    from validation.reference import collect

    counts = Counter(agent_calls=0, decision_rows=0, gauss_api_calls=0,
                     inaccessible_visits=0, empty_calls=0, gaussian_cache_hits=0)
    visits = []
    submit = FCNAgent.submit_orders.__code__
    decision = FCNAgent.submit_orders_by_market.__code__

    def observe(frame, event, result):
        code = frame.f_code
        if code == submit:
            if event == "call":
                counts["agent_calls"] += 1
            elif event == "return" and result == []:
                counts["empty_calls"] += 1
        elif (event == "return" and code == Agent.is_market_accessible.__code__
              and frame.f_back.f_code == decision):
            visits.append([frame.f_locals["self"].agent_id, frame.f_locals["market_id"], result])
            counts["decision_rows"] += result
            counts["inaccessible_visits"] += not result
        elif (event == "call" and code == random.Random.gauss.__code__
              and frame.f_back.f_code == decision):
            counts["gauss_api_calls"] += 1
            counts["gaussian_cache_hits"] += frame.f_locals["self"].gauss_next is not None

    sys.setprofile(observe)
    try:
        trace = collect(read(config), seed, PAMS)
    finally:
        sys.setprofile(None)
    write(directory / "reference.json.gz", trace)
    initial_cache = {
        key: value["python_random"][2]
        for key, value in trace["initial"]["rng"].items()
        if key.startswith("agents/") and key.endswith("/prng") and value["python_random"][2] is not None
    }
    write(directory / "workload-observation.json", {**counts, "market_visits": visits,
                                                    "initial_agent_gauss_caches": initial_cache})


def load_records(run):
    from coreorder.schema import validate_record

    records = {name: read(run / f"{name}.json") for name in ("manifest", "metrics", "status", "environment")}
    for name, record in records.items():
        validate_record(name, record)
    assert records["manifest"]["git_sha"] == INPUT_SHA
    assert records["manifest"]["dirty"] is False
    native = records["environment"]["native_module"]
    if native:
        from coreorder.config import sha256
        library = Path(native["path"])
        assert library.parent == ROOT / "build"
        assert native["sha256"] == sha256(library.read_bytes())
    return records


def verify(reference_trace, observed, run, evidence, expected):
    reference_counts = Counter(event["type"] for event in reference_trace["events"])
    trace = read(run / "validation-trace.json.gz")
    receipt = compare(reference_trace, trace)
    if receipt["status"] != "PASS":
        save_reproducer(reference_trace, trace, evidence / "first-difference")
        return {"status": "FAIL", "scope": "semantic", "first_difference": receipt["difference"]}
    records = load_records(run)
    manifest, metrics, status = (records[key] for key in ("manifest", "metrics", "status"))
    assert all(manifest[key] == value for key, value in expected.items())
    assert manifest["backend_requested"] == manifest["backend_effective"]
    from coreorder.config import sha256
    assert manifest["input_hash"] == sha256((run / "workload.json").read_bytes())
    assert manifest["effective_config_hash"] == sha256((run / "effective_config.json").read_bytes())
    assert manifest["environment_hash"] == sha256((run / "environment.json").read_bytes())
    effective = read(run / "effective_config.json")
    original = read(run / "workload.json")
    if manifest["book_restore"] == "incremental":
        for group in effective["simulation"]["markets"]:
            assert effective[group]["class"] == "CoreOrderMarket"
            if "class" in original[group]:
                effective[group]["class"] = original[group]["class"]
            else:
                del effective[group]["class"]
    assert effective == original
    work = {"orders": reference_counts["OrderLog"], "cancels": reference_counts["CancelLog"],
            "executions": reference_counts["ExecutionLog"], "expirations": reference_counts["ExpirationLog"],
            "market_steps": reference_counts["MarketStepEndLog"]}
    assert all(metrics[key] == value for key, value in work.items()), (metrics, work)
    if manifest["backend_effective"].startswith("native"):
        assert all(metrics[k] == observed[k] for k in ("agent_calls", "decision_rows", "gauss_api_calls"))
        assert metrics["native_rows"] == observed["decision_rows"]
        assert sum(metrics["batch_widths"]) == observed["agent_calls"]
        assert metrics["native_executor_creations"] == int(manifest["backend_effective"] == "native-parallel")
    invariant = check(trace)
    assert invariant["status"] == "PASS", invariant
    member_e = evaluate_cell(reference_trace, trace, manifest, status, expected)
    try:
        member_e_records(manifest, metrics, status)
        e_record = {"status": "PASS"}
    except ValueError as error:
        e_record = {"status": "FAIL", "reason": str(error)}
    result = {"status": "PASS", "semantic_comparison": receipt, "shared_records": "PASS",
              "workload": work, "checkpoints": len(trace["steps"]), "events": len(trace["events"]),
              "E_gate": member_e, "E_record": e_record}
    write(evidence / "assessment.json", result)
    return result


def run(output, core):
    output.mkdir()
    inputs = output / "inputs"
    inputs.mkdir()
    configs = member_e_cases(PAMS)
    prefilled = copy.deepcopy(configs["C01b-normal"])
    prefilled["FCNAgents"]["orderMargin"] = {"normal": [0.02, 0.0]}
    configs["C01b-prefilled-cache"] = prefilled
    inaccessible = copy.deepcopy(configs["C01c-all-empty"])
    inaccessible["FCNAgents"]["markets"] = []
    configs["C01d-zero-access"] = inaccessible
    zero_price = copy.deepcopy(configs["C01a-M1"])
    zero_price["FCNAgents"]["orderMargin"] = 1.0
    zero_price["FCNAgents"]["noiseScale"] = 0.002
    configs["C01k-fixed-zero-price"] = zero_price
    oracle = {}

    def collect_one(name, seed, config):
        key = (name, seed)
        if key in oracle:
            return oracle[key]
        directory = output / f"reference-{name}-{seed}"
        directory.mkdir()
        code = execute(directory / "command", (
            __file__, "reference", config, seed, directory,
        ))
        if code != 0:
            raise AssertionError((code, directory / "command/stderr.log"))
        trace, stats = (read(directory / filename) for filename in
                        ("reference.json.gz", "workload-observation.json"))
        assert check(trace)["status"] == "PASS"
        oracle[key] = trace, stats
        return oracle[key]

    all_rows = []
    for row in read(core / "status.json")["cases"]:
        base = core / row["case"]
        manifest = read(base / "manifest.json")
        workload = manifest["workload_id"]
        seed = manifest["seed"]
        known, stats = collect_one(workload, seed, base / "workload.json")
        prior = read(core / f"{workload}-reference.json.gz")
        assert compare(prior, known)["status"] == "PASS"
        evidence = output / row["case"]
        evidence.mkdir()
        result = verify(known, stats, base, evidence, {
            "backend_effective": manifest["backend_effective"], "book_restore": manifest["book_restore"],
            "layout": manifest["layout"], "workers": manifest["workers"],
        })
        all_rows.append({"case": row["case"], **result})

    extra = [(name, 101, 4, "soa", 2, "dynamic") for name in configs]
    extra += [("C01e-four-markets", 202, workers, layout, grain, schedule)
              for workers in (1, 2, 4) for layout in ("aos", "soa")
              for grain, schedule in ((2, "static"), (3, "dynamic"))]
    extra += [("C01b-prefilled-cache", 303, 2, "aos", 3, "static"),
              ("C01h-MarketMaker", 303, 2, "aos", 3, "static")]
    for name, seed, workers, layout, grain, schedule in extra:
        config = inputs / f"{name}.json"
        if not config.exists():
            write(config, configs[name])
        trace, observed = collect_one(name, seed, config)
        label = f"{name}-{seed}-w{workers}-{layout}-{schedule}"
        dest = output / label
        dest.mkdir()
        run_path = dest / "run"
        code = execute(dest / "command", (
            "-m", "coreorder", "run", "--config", config, "--seed", seed, "--output", run_path,
            "--backend", "native-parallel", "--book-restore", "incremental", "--layout", layout,
            "--workers", workers, "--grain", grain, "--schedule", schedule, "--validation-trace",
        ))
        if code == 0:
            result = verify(trace, observed, run_path, dest, {
                "backend_effective": "native-parallel", "book_restore": "incremental", "seed": seed,
                "workers": workers, "layout": layout, "grain": grain, "schedule": schedule,
            })
        else:
            result = {"status": "TIMEOUT" if code is None else "FAIL", "exit": code}
        print(label, result["status"], flush=True)
        all_rows.append({"case": label, **result})
    summary = {
        "semantic": dict(Counter(row["status"] for row in all_rows)),
        "E_gate": dict(Counter(row.get("E_gate", {}).get("status") for row in all_rows)),
        "E_record": dict(Counter(row.get("E_record", {}).get("status") for row in all_rows)),
        "cases": all_rows,
    }
    write(output / "summary.json", summary)
    print({key: summary[key] for key in ("semantic", "E_gate", "E_record")}, flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "reference":
        reference(Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]))
    else:
        run(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
