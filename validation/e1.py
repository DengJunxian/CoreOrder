"""CoreOrder's G0 adapter for the independent E reference and comparator."""

import argparse
import subprocess
import sys
from pathlib import Path

from coreorder.config import ROOT, load_workload, sha256
from coreorder.environment import environment
from coreorder.runner import run_py_seq

from .codec import digest, snapshot
from .collector import ObservedSimulator, TraceLogger
from .compare import compare, save_reproducer
from .io import read, write


def compare_case(name, config, seed, output, env):
    output.mkdir()
    raw = config.read_bytes()
    workload = output / "workload.json"
    workload.write_bytes(raw)
    reference_path = output / "reference.json.gz"
    candidate_path = output / "candidate.json.gz"
    command = [
        sys.executable, "-m", "validation", "collect", "--config", str(workload),
        "--seed", str(seed), "--pams-root", str(ROOT / "vendor/pams"),
        "--output", str(reference_path),
    ]
    write(output / "reference_command.json", {"argv": command, "cwd": str(ROOT)})
    with (output / "reference.stdout.log").open("x") as stdout, (output / "reference.stderr.log").open("x") as stderr:
        result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, check=False)
    write(output / "reference_exit.json", {"exit_code": result.returncode})
    result.check_returncode()

    logger = TraceLogger()

    initial = None

    def after_setup(runner):
        nonlocal initial
        logger.runner_rng = runner._prng
        initial = snapshot(runner.simulator, runner._prng)

    settings = load_workload(raw)
    runner, _ = run_py_seq(workload, seed, logger, simulator_class=ObservedSimulator, after_setup=after_setup)
    final = snapshot(runner.simulator, runner._prng)
    candidate = {
        "contract_version": env["contract_version"], "upstream_sha": env["upstream"]["PAMS"]["sha"],
        "config": settings, "input_hash": digest(settings), "seed": seed,
        "backend_effective": "py-seq", "book_restore": "upstream",
        "initial": initial, "events": logger.events, "steps": logger.steps, "final": final, "rng": final["rng"],
    }
    write(candidate_path, candidate)
    reference = read(reference_path)
    report = compare(reference, candidate)
    write(output / "comparison.json", report)
    if report["status"] == "FAIL":
        save_reproducer(reference, candidate, output / "first-divergence", str(reference_path), str(candidate_path))
    receipt = {
        "name": name, "status": report["status"], "config_sha256": sha256(raw),
        "events": len(logger.events), "checkpoints": len(logger.steps),
    }
    print(receipt, flush=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("smoke", "g0"), required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    env = environment()
    write(args.output / "environment.json", env)
    pams = env["upstream"]["PAMS"]
    if (
        pams["dirty"] or pams["sha"] != pams["required_sha"]
        or env["pams_install_source"] != (ROOT / "vendor/pams").as_uri()
        or env["pams_version"] != pams["required_version"]
        or not env["pams_distribution_matches_import"]
    ):
        raise ValueError("G0 requires a clean PAMS checkout and an installation from that checkout")

    workloads = [("smoke", args.config)]
    if args.suite == "g0":
        workloads.append(("event-state", ROOT / "fixtures/pams/event-state/config.json"))
    cases = [compare_case(name, config, args.seed, args.output / name, env) for name, config in workloads]
    passed = all(case["status"] == "PASS" for case in cases)
    receipt = {
        "suite": args.suite, "contract_version": env["contract_version"], "git_sha": env["git_sha"],
        "seed": args.seed, "status": "PASS" if passed else "FAIL", "cases": cases,
        "checks": dict.fromkeys(("events", "step_state", "final_rng"), "PASS" if passed else "FAIL"),
    }
    write(args.output / "status.json", receipt)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
