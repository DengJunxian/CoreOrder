"""Compare the system candidate with E's independently collected PAMS trace."""

import sys
from pathlib import Path

from jsonschema import ValidationError

from experiments.capture import execute as capture
from validation.compare import save_reproducer
from validation.gate import evaluate_cell
from validation.invariants import check
from validation.io import read, write
from validation.records import validate_record as validate_e_record

from .config import ROOT, sha256
from .contracts import CONTRACT_VERSION
from .environment import git
from .schema import validate_record

SEED = 42


def execute(prefix, args):
    command = [sys.executable, "-B", "-m", *map(str, args)]
    return capture(command, prefix.with_name(f"{prefix.name}-command"), 120, cwd=ROOT,
                   scope="local technical differential and E record checks")


def cases():
    for restore in ("upstream", "incremental"):
        for backend, workers in (("py-seq", 1), ("py-thread", 2), ("py-process", 2)):
            yield "native-serial-normal", restore, backend, workers, None, None, None
        for layout in ("aos", "soa"):
            yield "native-serial-normal", restore, "native-serial", 1, layout, None, None
            for workers in (1, 2, 4):
                schedule = "dynamic" if workers == 4 else "static"
                yield "native-serial-normal", restore, "native-parallel", workers, layout, 2, schedule
    yield "smoke", "upstream", "py-seq", 1, None, None, None
    yield "smoke", "upstream", "native-serial", 1, "aos", None, None
    yield "smoke", "incremental", "native-parallel", 4, "soa", 1, "dynamic"
    yield "p09-full-quota", "upstream", "py-seq", 1, None, None, None
    yield "p09-full-quota", "incremental", "native-parallel", 4, "soa", 3, "static"


def run(output, *, selected=None, suite="g2"):
    output.mkdir(parents=True, exist_ok=False)
    oracle = {}
    results = []
    revision = git("rev-parse", "HEAD")
    for workload, restore, backend, workers, layout, grain, schedule in cases() if selected is None else selected:
        settings = ROOT / "configs/workloads" / f"{workload}.json"
        if workload not in oracle:
            reference_path = output / f"{workload}-reference.json.gz"
            reference_attempt = execute(output / f"{workload}-reference", (
                "validation", "collect", "--config", settings, "--seed", SEED,
                "--pams-root", ROOT / "vendor/pams", "--output", reference_path,
            ))
            if reference_attempt["status"] != "PASS":
                raise RuntimeError(f"E could not collect the original PAMS reference for {workload}")
            reference = read(reference_path)
            invariants = check(reference)
            write(output / f"{workload}-reference-invariants.json", invariants)
            if invariants["status"] != "PASS":
                raise RuntimeError(f"PAMS reference invariants failed for {workload}")
            oracle[workload] = reference

        label = f"{workload}-{restore}-{backend}-w{workers}-{layout or 'na'}"
        directory = output / label
        command = ["coreorder", "run", "--config", settings, "--seed", SEED, "--output", directory,
                   "--backend", backend, "--workers", workers, "--book-restore", restore, "--validation-trace"]
        if layout:
            command.extend(("--layout", layout))
        if grain is not None:
            command.extend(("--grain", grain, "--schedule", schedule))
        launch = execute(output / label, command)
        code = launch["exit_code"]
        result = {"case": label, "backend": backend, "exit": code, "status": launch["status"]}
        if launch["status"] == "PASS":
            result["status"] = "FAIL"
            records = {name: read(directory / f"{name}.json") for name in
                       ("manifest", "environment", "status", "metrics")}
            for name, record in records.items():
                validate_record(name, record)
            manifest, status, metrics = (records[name] for name in ("manifest", "status", "metrics"))
            assert manifest["git_sha"] == revision
            assert manifest["input_hash"] == sha256(settings.read_bytes())
            assert manifest["effective_config_hash"] == sha256((directory / "effective_config.json").read_bytes())
            assert manifest["backend_requested"] == manifest["backend_effective"] == backend
            assert manifest["workers"] == workers and manifest["book_restore"] == restore
            assert manifest["layout"] == (layout or "not_applicable")
            assert status["status"] == "PASS"
            candidate = read(directory / "validation-trace.json.gz")
            expected = {"backend_requested": backend, "book_restore": restore, "workers": workers,
                        "layout": layout or ("aos" if backend.startswith("native") else "not_applicable"),
                        "grain": grain, "schedule": schedule}
            report = evaluate_cell(oracle[workload], candidate, manifest, status, expected)
            write(directory / "comparison.json", report)
            try:
                validate_e_record(manifest, metrics, status)
                e_record = {"status": "PASS"}
            except (ValueError, ValidationError) as error:
                e_record = {"status": "FAIL", "reason": str(error)}
            write(directory / "e-record.json", e_record)
            invariants = check(candidate)
            write(directory / "invariants.json", invariants)
            if report.get("scope"):
                save_reproducer(oracle[workload], candidate, directory / "first-divergence")
            if backend.startswith("native"):
                assert metrics["native_executor_creations"] == int(backend == "native-parallel")
                assert metrics["native_rows"] > 0
            if backend == "py-process":
                copy = read(directory / "process_copy.json")
                assert copy["start_method"] == "spawn" and copy["serialized_dispatch_bytes"] > 0
                result["process_copy"] = copy
            result.update(comparison=report["status"], e_record=e_record["status"], invariants=invariants["status"],
                          events=len(candidate["events"]), checkpoints=len(candidate["steps"]),
                          configuration_sha256=manifest["input_hash"],
                          native_executor_creations=metrics.get("native_executor_creations"),
                          **{key: status[key] for key in ("trace_hash", "final_state_hash", "rng_hash")})
            if report["status"] == invariants["status"] == e_record["status"] == "PASS":
                result["status"] = "PASS"
        elif code == 2 and (directory / "status.json").is_file():
            if read(directory / "status.json")["status"] == "UNSUPPORTED":
                result["status"] = "UNSUPPORTED"
        results.append(result)
        print(label, result["status"], flush=True)
    status = "PASS" if all(result["status"] == "PASS" or result["backend"] == "py-process"
                           and result["status"] in ("TIMEOUT", "UNSUPPORTED") for result in results) else "FAIL"
    write(output / "status.json", {"contract_version": CONTRACT_VERSION, "suite": suite, "git_sha": revision,
                                  "scope": "local technical differential and E record checks",
                                  "status": status, "seed": SEED, "cases": results})
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(run(Path(sys.argv[1]).resolve()))
