"""Run identity, immutable attempt records and independent validation bindings."""

import re
from contextlib import suppress
from pathlib import Path
from time import perf_counter

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from coreorder.config import ROOT, json_bytes, sha256
from coreorder.environment import environment
from coreorder.native_serial import load_native_serial
from coreorder.schema import validate_record
from validation import CONTRACT, PAMS_SHA
from validation.io import read
from validation.records import STATUSES, TIMES, validate_record as validate_metrics

from .protocol import SETTINGS, TOKEN, condition, file_hash, require

RECEIPT_FORMAT = "r4-validation-receipt-v1"
RUN_ID = re.compile(r"[0-9a-f]{32}")


def runtime_identity(record, native_sha):
    return {
        "git_sha": record["git_sha"], "dirty": record["dirty"], "host_id": record["host_id"],
        "architecture": record["architecture"], "compiler": record["compiler"],
        "environment_sha256": sha256(json_bytes(record)),
        "dependency_lock_hash": record["dependency_lock_hash"],
        "upstream_shas": {name: dependency["sha"] for name, dependency in record["upstream"].items()},
        "native_sha256": native_sha,
        "schemas_sha256": {name: file_hash(ROOT / name) for name in
                           ("schemas/records.schema.json", "schemas/run_config.schema.json", "schemas/workload.schema.json")},
    }


def inspect_environment(protocol, native):
    record = environment()
    validate_record("environment", record)
    require(record["upstream"] == protocol.lock["upstream"], "actual upstream identity differs from the protocol")
    require(record["dependency_lock_hash"] == protocol.lock["dependency_lock_hash"], "dependency lock differs")
    require(record["pams_install_source"] == (ROOT / "vendor/pams").as_uri() and
            record["pams_distribution_matches_import"] and
            record["pams_version"] == record["upstream"]["PAMS"]["required_version"], "PAMS installation differs")
    packages = {canonicalize_name(name): version for name, version in record["packages"].items()}
    for line in (ROOT / "requirements.lock").read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        requirement = Requirement(line)
        if requirement.marker is None or requirement.marker.evaluate():
            name = canonicalize_name(requirement.name)
            require(name in packages and requirement.specifier.contains(packages[name]), f"locked dependency differs: {name}")
    module = load_native_serial() if native else None
    if module is not None:
        require(hasattr(module, "executor_creations"), "integrated native extension required")
    return record, runtime_identity(record, file_hash(Path(module.__file__).resolve()) if module else None)


def manifest_for(protocol, row, runtime, scope, run_id):
    identity = condition(protocol.workloads[row["workload"]], row, runtime)
    requested = identity.pop("backend")
    return {
        **identity, "run_id": run_id, "case_id": row["id"], "experiment_id": row["phase"], "scope": scope,
        "workload_id": row["workload"], "protocol_hash": protocol.identity, "contract_version": CONTRACT,
        "upstream_sha": PAMS_SHA, "environment_hash": runtime["environment_sha256"],
        "backend_requested": requested, "backend_effective": None,
        "variant": row.get("variant"), "repeat": row.get("repeat", 0), "warmup": row.get("warmup", False),
        "pairing_group_id": row.get("group"), "block_id": row.get("block_id"),
        "order_seed": row.get("order_seed"), "order_position": row.get("order_position"),
        "validation_run_id": None,
        "pairing_not_applicable_reason": (
            "planned warmup" if row.get("warmup") else "unpaired correctness/diagnostic"
        ) if row.get("block_id") is None else None,
    }


def missing_metrics(mode, reason):
    return {"measurement_mode": mode, **dict.fromkeys(TIMES),
            "missing_reasons": dict.fromkeys(TIMES, reason), "metric_sources": {}}


def verify_child(protocol, row, runtime, run_id, output, mode):
    core, metrics, status, environment = (read(output / f"{key}.json") for key in
                                        ("manifest", "metrics", "status", "environment"))
    for name, obj in zip(("manifest", "metrics", "status", "environment"), (core, metrics, status, environment)):
        validate_record(name, obj)
    workload = protocol.workloads[row["workload"]]
    expected = condition(workload, row, runtime)
    keys = ("git_sha", "dirty", "host_id", "seed", "numeric_mode", "input_hash", "canonical_input_hash",
            "effective_config_hash",
            *[key for key in SETTINGS if key != "backend"])
    require(all(core[key] == expected[key] for key in keys) and core["upstream_shas"] == expected["upstream_shas"],
            "child run identity mismatch")
    require(core["backend_requested"] == core["backend_effective"] == expected["backend"] and
            core["run_id"] == status["run_id"] == run_id and status["status"] == "PASS", "child backend or run ID differs")
    require(metrics["measurement_mode"] == mode and core["protocol"]["measurement_mode"] == mode,
            "child measurement mode differs")
    require(file_hash(output / "workload.json") == expected["input_hash"] and
            file_hash(output / "effective_config.json") == expected["effective_config_hash"] and
            file_hash(output / "environment.json") == core["environment_hash"], "child inputs or environment differ")
    require((core["N"], core["K"], core["max_normal_orders_by_session"], core["steps"]) ==
            (workload["N"], workload["K"], workload["M_by_session"], sum(workload["steps_by_session"])),
            "child realized workload differs from plan")
    module = environment["native_module"]
    require((module is not None) == expected["backend"].startswith("native") and
            (module is None or module["sha256"] == expected["native_sha256"]), "child native binary differs")
    require(runtime_identity({**environment, "native_module": None}, expected["native_sha256"]) == runtime,
            "child actual environment differs")
    for filename, key in (("final_state.json", "final_state_hash"), ("final_rng.json", "rng_hash")):
        require(file_hash(output / filename) == status[key], f"child {filename} digest differs")
    if module is not None:
        require(type(metrics["native_rows"]) is int and metrics["native_rows"] >= 0 and
                metrics["decision_rows"] == metrics["native_rows"] and
                metrics["native_executor_creations"] == int(expected["backend"] == "native-parallel"),
                "native workload or executor count differs")
    return metrics, status


def seal(directory, record, started):
    validate_metrics(record["manifest"], record["metrics"], record["status"])
    publish(directory / "record.json", record)
    files = evidence_files(directory)
    publish(directory / "seal.json", {"files_sha256": files, "elapsed_s": perf_counter() - started})


def publish(path, value):
    temporary = path.with_suffix(".pending")
    require(not path.exists(), f"immutable file exists: {path}")
    with suppress(FileNotFoundError):
        temporary.unlink()
    with temporary.open("xb") as output:
        output.write(json_bytes(value))
    temporary.replace(path)


def evidence_files(directory):
    hashes = {}
    for path in sorted(directory.rglob("*")):
        require(not path.is_symlink(), f"symbolic link in raw evidence: {path}")
        if path.is_file() and path != directory / "seal.json":
            hashes[path.relative_to(directory).as_posix()] = file_hash(path)
    return hashes


def read_attempts(root):
    result = {}
    run_ids = set()
    raw = root / "raw"
    if not raw.exists():
        return result
    require(raw.is_dir() and not raw.is_symlink(), "invalid raw root")
    for case_dir in sorted(raw.iterdir()):
        require(case_dir.is_dir() and not case_dir.is_symlink() and TOKEN.fullmatch(case_dir.name),
                f"invalid raw case directory: {case_dir}")
        entries = list(case_dir.iterdir())
        require(len(entries) == 1, f"expected one immutable attempt: {case_dir}")
        directory = entries[0]
        require(directory.is_dir() and not directory.is_symlink() and RUN_ID.fullmatch(directory.name) and
                directory.name not in run_ids, "invalid or duplicate run ID")
        seal_file = directory / "seal.json"
        require(seal_file.is_file() and not seal_file.is_symlink(), f"unsealed attempt: {directory}")
        proof = read(directory / "seal.json")
        require(proof["files_sha256"] == evidence_files(directory), f"tampered raw data: {directory}")
        record = read(directory / "record.json")
        manifest, metrics, status = (record[key] for key in ("manifest", "metrics", "status"))
        require(manifest["case_id"] == case_dir.name and manifest["run_id"] == directory.name and
                status["run_id"] == directory.name and status["status"] in STATUSES, "raw identity mismatch")
        validate_metrics(manifest, metrics, status)
        require((manifest["backend_effective"] == manifest["backend_requested"]) if status["status"] == "PASS"
                else manifest["backend_effective"] is None, "raw effective backend differs")
        require(type(proof["elapsed_s"]) in (int, float) and 0 <= proof["elapsed_s"] < float("inf"),
                "invalid charged duration")
        if record["command"] is not None:
            require(record["command"] in ("launch/command.json", "core/launch/command.json"),
                    "invalid raw command reference")
            launch = read(directory / record["command"])
            require(0 <= launch["elapsed_s_driver"] <= proof["elapsed_s"], "raw duration is less than child duration")
        run_ids.add(directory.name)
        result[case_dir.name] = {"directory": directory, "record": record, "elapsed_s": proof["elapsed_s"],
                                 "files_sha256": proof["files_sha256"]}
    return result


def validation_binding(attempt, identity, attempts, approved=None):
    path = attempt["directory"] / "validation-receipt.json"
    require(path.is_file(), "missing independent validation receipt")
    receipt = read(path)
    manifest, status = (attempt["record"][key] for key in ("manifest", "status"))
    require(receipt["format"] == RECEIPT_FORMAT and receipt["identity"] == identity and
            receipt["run_id"] == manifest["run_id"] and receipt["case_id"] == manifest["case_id"] and
            status["status"] == status["validation_status"] == "PASS" and
            attempt["record"]["metrics"]["measurement_mode"] == "validation", "validation receipt identity mismatch")
    require(receipt["production_final"] == {key: status[key] for key in ("final_state_hash", "rng_hash")},
            "validation final digest mismatch")
    oracle = attempts.get(receipt["reference_case_id"])
    require(oracle is not None and oracle["record"]["status"]["status"] == "PASS", "oracle raw evidence is missing")
    oracle_manifest = oracle["record"]["manifest"]
    require(oracle_manifest["run_id"] == receipt["reference_run_id"] == status["reference_run_id"] and
            oracle_manifest["backend_effective"] == "py-seq" and oracle_manifest["book_restore"] == "upstream" and
            all(oracle_manifest[key] == identity[key] for key in
                ("input_hash", "canonical_input_hash", "seed", "git_sha", "host_id", "environment_sha256")),
            "oracle identity mismatch")
    require(receipt["evidence"] == {
                "trace": attempt["files_sha256"]["core/validation-trace.json.gz"],
                "reference": oracle["files_sha256"]["oracle-trace.json.gz"],
                "comparison": attempt["files_sha256"]["core/comparison.json"],
                "invariants": attempt["files_sha256"]["invariants.json"],
                "oracle_invariants": oracle["files_sha256"]["invariants.json"],
            } and read(attempt["directory"] / "core/comparison.json")["status"] == "PASS" and
            read(attempt["directory"] / "invariants.json")["status"] == "PASS" and
            read(oracle["directory"] / "invariants.json")["status"] == "PASS", "validation proof mismatch")
    binding = {"run_id": receipt["run_id"], "sha256": file_hash(path)}
    gate = attempt["directory"] / "e-gate.json"
    if approved is not None or gate.is_file():
        require(gate.is_file() and read(gate)["status"] == "PASS", "independent E record gate evidence is missing")
    require(approved is None or binding == approved, "receipt is not the exact G3-approved V01 receipt")
    return receipt, binding
