"""Replay the pinned Member E oracle against the integrated P05 serial entry point."""

import argparse
import io
import itertools
import json
from pathlib import Path
import platform
import subprocess
import sys
import tarfile

from audit_p06 import (C01_SEEDS, E_SHA, PAMS, ROOT, VENDOR, c01_config, digest, git, json_bytes,
                       probe_config, verify_candidate)

HEAP_FIXTURES = (
    "C01a-M1", "C01b-normal", "C01e-four-markets",
    "C01g-fundamental-shock", "C01g-placement-stopped", "C01h-MarketMaker",
)


def export_e(output):
    directory = output / "member-e"
    directory.mkdir()
    archive = subprocess.check_output(
        ["git", "archive", E_SHA, "validation"], cwd=ROOT
    )
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(directory, filter="data")
    return directory


def candidate(config, seed, folder):
    from coreorder.config import incremental_workload
    from coreorder.market_adapter import CoreOrderMarket
    from coreorder.runner import run_py_seq
    from validation import CONTRACT, PAMS_SHA
    from validation.codec import digest, snapshot
    from validation.collector import ObservedSimulator, TraceLogger

    effective = folder / "effective_config.json"
    effective.write_text(json.dumps(incremental_workload(config)) + "\n", encoding="utf-8")
    logger = TraceLogger()
    initial = {}

    def after_setup(runner):
        logger.runner_rng = runner._prng
        initial.update(snapshot(runner.simulator, runner._prng))

    runner, _ = run_py_seq(
        effective, seed, logger, book_restore="incremental",
        simulator_class=ObservedSimulator, after_setup=after_setup,
    )
    assert all(type(m) is CoreOrderMarket for m in runner.simulator.markets)
    logger._process()
    final = snapshot(runner.simulator, runner._prng)

    # The mode is run metadata. Keep every other E-encoded market field.
    for state in itertools.chain((initial,), (step["state"] for step in logger.steps), (final,)):
        for market in state["markets"]:
            assert market.pop("book_restore") == "incremental"
    return {
        "contract_version": CONTRACT, "upstream_sha": PAMS_SHA, "config": config,
        "input_hash": digest(config), "seed": seed, "backend_effective": "py-seq",
        "book_restore": "incremental", "initial": initial,
        "events": logger.events, "steps": logger.steps, "final": final, "rng": final["rng"],
    }


def workloads():
    for seed, margin, ttl in itertools.product((42, 20261125), ("fixed", "normal"), ((3, 6), (100, 200))):
        name = f"probe-{margin}-{ttl[0]}-{ttl[1]}"
        yield name, seed, json_bytes(probe_config(margin, ttl))
    for name in HEAP_FIXTURES:
        raw = c01_config(name)
        for seed in C01_SEEDS:
            yield name, seed, raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--current", action="store_true", help="re-run Member E's checks on the integrated candidate")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True)
    tested = verify_candidate(args.current)
    e_source = export_e(output)
    sys.path.insert(0, str(e_source))

    from validation import CONTRACT, PAMS_SHA
    from validation.compare import compare, first_diff, save_reproducer
    from validation.invariants import check
    from validation.io import write
    from validation.reference import collect
    from validation.upstream import verify_source

    assert PAMS_SHA == PAMS
    assert verify_source(VENDOR) == VENDOR
    info = {
        "member_e_sha": E_SHA, "candidate_source_sha": tested, "runner_checkout_sha": git("rev-parse", "HEAD"),
        "pams_sha": PAMS, "contract": CONTRACT, "python": platform.python_version(),
        "platform": platform.platform(), "member_e_validation_tree": git("rev-parse", f"{E_SHA}:validation"),
    }
    write(output / "identity.json", info)
    print(json.dumps(info), flush=True)

    cases = []
    for name, seed, raw in workloads():
        config = json.loads(raw)
        folder = output / f"{name}-{seed}"
        folder.mkdir()
        (folder / "workload.json").write_bytes(raw)
        reference = collect(config, seed, VENDOR)
        optimized = candidate(config, seed, folder)
        write(folder / "reference.json.gz", reference)
        write(folder / "incremental.json.gz", optimized)
        comparison = compare(reference, optimized)
        initial_difference = first_diff(reference["initial"], optimized["initial"])
        if initial_difference is not None:
            comparison = {"status": "FAIL", "scope": "initial", "difference": initial_difference}
        invariants = {mode: check(trace) for mode, trace in (("upstream", reference), ("incremental", optimized))}
        row = {
            "case": name, "seed": seed, "input_hash": reference["input_hash"],
            "input_sha256": digest(raw), "checks": comparison,
            "invariants": invariants, "events": len(reference["events"]), "steps": len(reference["steps"]),
            "fills": sum(e["type"] == "ExecutionLog" for e in reference["events"]),
            "expirations": sum(e["type"] == "ExpirationLog" for e in reference["events"]),
        }
        write(folder / "comparison.json", row)
        statuses = [comparison["status"], *(value["status"] for value in invariants.values())]
        print(f"{name} seed={seed} diff/upstream/incremental={statuses} events={row['events']} "
              f"steps={row['steps']} fills={row['fills']} expirations={row['expirations']} "
              f"config={row['input_hash']}", flush=True)
        if comparison["status"] == "FAIL":
            if comparison["scope"] == "initial":
                write(folder / "first_divergence.json", comparison)
            else:
                save_reproducer(reference, optimized, folder / "first-divergence",
                                str(folder / "reference.json.gz"), str(folder / "incremental.json.gz"))
        if statuses != ["PASS", "PASS", "PASS"]:
            return 1
        cases.append(row)
    assert len(cases) == 8 + 5 * len(HEAP_FIXTURES)
    write(output / "summary.json", {**info, "status": "PASS", "pairs": len(cases), "cases": cases})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
