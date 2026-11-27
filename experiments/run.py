"""Execute the frozen CoreOrder schedule with independent semantic admission."""

import argparse
import os
import subprocess
import sys
import tempfile
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter

from jsonschema import ValidationError

from coreorder.cli import main as coreorder
from coreorder.config import ROOT, json_bytes, sha256
from validation.gate import evaluate_cell
from validation.stream import compare_streams, conservation, inventory, metadata
from validation.io import read, write

from .capture import execute
from .evidence import (RECEIPT_FORMAT, RUN_ID, inspect_environment, manifest_for, missing_metrics, read_attempts,
                       seal, validation_binding, verify_child)
from .protocol import DEFAULT, Protocol, condition, file_hash, is_oracle, positive, require

HOST_LOCK = Path(tempfile.gettempdir()) / "coreorder-r4-experiment.lock"
HOST_LEASE = HOST_LOCK.with_suffix(".active.json")
FORMAL = ("timing", "E05")


def stage_rows(protocol, stage, cases):
    if stage == "pilot":
        require(not cases, "--case applies only to C01 or V01")
        return protocol.pilot()[0]
    if stage in FORMAL:
        require(not cases, "select a whole authorized stage for formal execution")
        require(protocol.active, "G3 BLOCKED: formal execution requires an effective G3 lock")
        authorized = set(protocol.plan["authorized_formal_runs"])
        return [row for row in protocol.rows[stage] if row["id"] in authorized]
    require(len(cases) == len(set(cases)), "duplicate selected case")
    by_id = {row["id"]: row for row in protocol.rows[stage]}
    require(set(cases) <= by_id.keys(), f"unknown {stage} case")
    selected = set(cases) | {by_id[key]["reference"] for key in cases if not is_oracle(by_id[key])}
    return [row for row in protocol.rows[stage] if not cases or row["id"] in selected]


def scope_for(stage, protocol=None):
    if protocol is not None and protocol.research and stage in FORMAL:
        return {"timing": "a-authorized-timing", "E05": "a-authorized-diagnostic"}[stage]
    return {"pilot": "development-pilot", "timing": "formal-timing", "E05": "formal-diagnostic"}.get(
        stage, "candidate-validation",
    )


def mode_for(row):
    return row.get("mode", {"E05-PMU": "pmu", "E05-profile": "profile", "E05-replay": "replay"}.get(
        row["phase"], "timing" if "group" in row else "validation",
    ))


@contextmanager
def exclusive_host(acknowledge, root):
    with HOST_LOCK.open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            if not lock.tell():
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
        else:
            import fcntl
        try:
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError("another CoreOrder experiment owns the host lock") from error
        if HOST_LEASE.exists():
            lease = read(HOST_LEASE)
            owner = Path(lease["directory"]).resolve()
            require(acknowledge and owner.is_relative_to(root / "raw"),
                    f"unconfirmed previous process tree at {owner}; verify it exited before acknowledging")
            write(owner / "interruption-acknowledgement.json",
                  {"operator_confirmed_process_tree_exited": True, "previous_lease": lease})
            HOST_LEASE.unlink()
        yield


def qualify_external(protocol, runtime, receipt_root):
    approved = protocol.approval(runtime)
    require(receipt_root is not None, "formal run requires the sealed V01 raw batch")
    batch = read(receipt_root / "batch.json")
    require(batch["stage"] == "V01" and batch["runtime"] == runtime, "V01 source batch does not match target runtime")
    attempts = read_attempts(receipt_root)
    bindings = {}
    for key, approval in approved.items():
        require(key in attempts, f"approved V01 attempt is missing: {key}")
        row = protocol.index[key]
        receipt, binding = validation_binding(
            attempts[key], condition(protocol.workloads[row["workload"]], row, runtime), attempts, approval,
        )
        require(receipt["reference_case_id"] == row["reference"], f"unexpected V01 oracle for {key}")
        bindings[key] = (receipt, binding)
    return bindings


def bind_attempt(row, protocol, runtime, attempts, external):
    mode = mode_for(row)
    if mode == "validation" or mode == "replay":
        return None, None
    key = row.get("v01")
    if key is None:
        key = next((candidate["id"] for candidate in protocol.rows["V01"] if not is_oracle(candidate) and
                    candidate["seed"] == row["seed"] and candidate["settings"] == row["settings"] and
                    protocol.same_input(candidate, row)), None)
    identity = condition(protocol.workloads[row["workload"]], row, runtime)
    if external is not None:
        require(key in external, "missing formal validation binding")
        receipt, binding = external[key]
        require(receipt["identity"] == identity, "V01 condition differs from timed run")
    else:
        require(key in attempts, "independent validation attempt is missing")
        receipt, binding = validation_binding(attempts[key], identity, attempts)
    return receipt, {"case_id": key, **binding}


def parent_core_args(row, workload, directory, run_id, timeout, mode, reference, protocol):
    settings = row["settings"]
    args = ["run", "--mode", mode, "--output", str(directory / "core"), "--config", str(workload["file"]),
            "--seed", str(row["seed"]), "--_run-id", run_id, "--timeout", str(timeout),
            "--backend", settings["backend"], "--book-restore", settings["book_restore"],
            "--workers", str(settings["workers"])]
    if settings["layout"] != "not_applicable":
        args.extend(("--layout", settings["layout"]))
    if settings["grain"] is not None:
        args.extend(("--grain", str(settings["grain"]), "--schedule", settings["schedule"]))
    if reference is not None:
        args.extend(("--reference-trace", str(reference), "--stream-validation"))
    if mode == "pmu":
        events = row["events"]
        qualified = protocol.lock["primary_x86"]["actual_pmu_events"] or {}
        require(protocol.plan["diagnostics"]["PMU_enabled"] and events and
                events == qualified.get(row["event_group"]), "PMU event group is unqualified")
        for event in events:
            args.extend(("--pmu-event", event))
    return args


def launch_attempt(directory, row, workload, run_id, timeout, mode, reference, protocol, external):
    if is_oracle(row):
        command = [sys.executable, "-m", "validation", "collect", "--config", str(workload["file"]), "--seed",
                   str(row["seed"]), "--pams-root", str(ROOT / "vendor/pams"), "--output",
                   str(directory / "oracle-trace.json.gz"), "--stream"]
        launch_file = "launch/command.json"
        callback = lambda: execute(command, directory / "launch", timeout, cwd=ROOT, scope="independent PAMS oracle")
    elif mode == "replay":
        from .replay import replay_command
        command = replay_command(protocol, row, directory, external)
        launch_file = "launch/command.json"
        callback = lambda: execute(command, directory / "launch", timeout, cwd=ROOT, scope="captured-row native replay")
    else:
        args = parent_core_args(row, workload, directory, run_id, timeout, mode, reference, protocol)
        launch_file = "core/launch/command.json"
        callback = lambda: coreorder(args)
    write(HOST_LEASE, {"directory": str(directory), "run_id": run_id})
    result = callback()
    launch = read(directory / launch_file)
    cleanup = launch.get("timeout_cleanup") or {}
    if "error" not in cleanup and "tree_kill_error" not in cleanup and cleanup.get("tree_kill_exit_code", 0) == 0:
        HOST_LEASE.unlink()
    code = result if type(result) is int else launch["exit_code"]
    return code, launch_file, launch


def validate_oracle(path, manifest, steps):
    trace = metadata(path)
    require(trace["input_hash"] == manifest["canonical_input_hash"] and trace["seed"] == manifest["seed"] and
            trace["upstream_sha"] == manifest["upstream_sha"] and trace["contract_version"] == manifest["contract_version"]
            and trace["backend_effective"] == "py-seq" and inventory(path)["steps"] == steps + 1,
            "independent oracle identity or checkpoint coverage mismatch")
    result = conservation(path)
    write(path.parent / "invariants.json", result)
    require(result["status"] == "PASS", "independent oracle invariant failure")


def issue_receipt(protocol, row, runtime, directory, manifest, status, oracle):
    path = directory / "core/validation-trace.json.gz"
    native = metadata(path)
    steps = sum(protocol.workloads[row["workload"]]["steps_by_session"])
    require(native["input_hash"] == manifest["canonical_input_hash"] and native["seed"] == manifest["seed"] and
            native["backend_effective"] == row["settings"]["backend"] and inventory(path)["steps"] == steps + 1,
            "candidate trace identity or checkpoint coverage differs")
    result = conservation(path)
    write(directory / "invariants.json", result)
    comparison = directory / "core/comparison.json"
    require(result["status"] == "PASS" and read(comparison)["status"] == "PASS", "independent comparison or invariants failed")
    core = read(directory / "core/manifest.json")
    reference = oracle["directory"] / "oracle-trace.json.gz"
    expected = {"backend_requested": row["settings"]["backend"], "book_restore": manifest["book_restore"],
                "layout": manifest["layout"], "workers": manifest["workers"]}
    gate = evaluate_cell(metadata(reference), native, core, status, expected,
                         compare_traces=lambda _ref, _candidate: compare_streams(reference, path))
    write(directory / "e-gate.json", gate)
    require(gate["status"] == "PASS", "E record and trace gate rejected the candidate")
    write(directory / "validation-receipt.json", {
        "format": RECEIPT_FORMAT, "identity": condition(protocol.workloads[row["workload"]], row, runtime),
        "case_id": row["id"], "run_id": manifest["run_id"], "reference_case_id": row["reference"],
        "reference_run_id": oracle["record"]["manifest"]["run_id"],
        "production_final": {key: status[key] for key in ("final_state_hash", "rng_hash")},
        "evidence": {"trace": file_hash(directory / "core/validation-trace.json.gz"),
                     "reference": oracle["files_sha256"]["oracle-trace.json.gz"], "comparison": file_hash(comparison),
                     "invariants": file_hash(directory / "invariants.json"),
                     "oracle_invariants": oracle["files_sha256"]["invariants.json"]},
    })


def attempt(protocol, row, runtime, scope, root, timeout, attempts, external, skip_reason=None):
    started = perf_counter()
    run_id = uuid.uuid4().hex
    directory = root / "raw" / row["id"] / run_id
    directory.mkdir(parents=True, exist_ok=False)
    write(directory / "started.json", {"case_id": row["id"], "run_id": run_id, "timeout_s": timeout})
    manifest = manifest_for(protocol, row, runtime, scope, run_id)
    mode = mode_for(row)
    status = {"run_id": run_id, "status": "NOT_RUN", "validation_status": "NOT_RUN", "censoring": None,
              "reference_run_id": None, "exit_code": None, "reason": skip_reason}
    metrics, launch_file, binding = missing_metrics(mode, "attempt did not complete"), None, None
    try:
        if skip_reason is None:
            oracle = attempts.get(row.get("reference"))
            reference = None
            if "reference" in row and not is_oracle(row):
                require(oracle is not None and oracle["record"]["status"]["status"] == "PASS",
                        "independent oracle did not pass")
                reference = oracle["directory"] / "oracle-trace.json.gz"
            receipt, binding = bind_attempt(row, protocol, runtime, attempts, external)
            if binding is not None:
                manifest["validation_run_id"] = binding["run_id"]
                status["validation_status"] = "PASS"
                status["reference_run_id"] = receipt["reference_run_id"]
            code, launch_file, launch = launch_attempt(directory, row, protocol.workloads[row["workload"]], run_id,
                                                       timeout, mode, reference, protocol, external)
            require(launch["git_sha"] == runtime["git_sha"] and launch["dirty"] == runtime["dirty"],
                    "launch checkout identity differs")
            status["exit_code"] = launch["exit_code"]
            if launch["status"] == "TIMEOUT":
                status.update(status="TIMEOUT", censoring="right", reason="attempt deadline exceeded")
            elif code != 0 or launch["status"] != "PASS":
                rejected = "UNSUPPORTED" if code == 2 else "FAIL"
                status.update(status=rejected, reason=f"command returned {code}; see {launch_file}")
            else:
                if is_oracle(row):
                    validate_oracle(directory / "oracle-trace.json.gz", manifest,
                                    sum(protocol.workloads[row["workload"]]["steps_by_session"]))
                elif mode == "replay":
                    metrics = {**metrics, "replay": read(directory / "replay.json")}
                    require(metrics["replay"]["native_sha256"] == runtime["native_sha256"] and
                            metrics["replay"]["backend"] == row["settings"]["backend"], "replay binary or backend differs")
                else:
                    measured, observed = verify_child(protocol, row, runtime, run_id, directory / "core", mode)
                    if mode == "validation":
                        require(observed["validation_status"] == "PASS", "independent comparison did not pass")
                        issue_receipt(protocol, row, runtime, directory, manifest, observed, oracle)
                        status.update(validation_status="PASS", reference_run_id=oracle["record"]["manifest"]["run_id"])
                    if receipt is not None:
                        require(receipt["production_final"] == {key: observed[key] for key in ("final_state_hash", "rng_hash")},
                                "timed/profile/PMU final state or RNG differs from validation")
                    if mode == "timing":
                        require(all(positive(measured[key]) and measured["metric_sources"].get(key) == "measured"
                                    for key in ("setup_s", "simulation_s", "process_wall_s")) and
                                measured["process_wall_s"] >= measured["setup_s"] + measured["simulation_s"],
                                "invalid production timer boundaries")
                    metrics = measured
                    status.update({key: observed[key] for key in ("final_state_hash", "rng_hash")})
                status["status"] = "PASS"
                manifest["backend_effective"] = row["settings"]["backend"]
    except (ValueError, KeyError, OSError, EOFError, ValidationError) as error:
        status.update(status="FAIL" if launch_file is not None else "NOT_RUN", reason=str(error))
        if mode == "validation":
            status["validation_status"] = "FAIL"
    outcome = {"manifest": manifest, "status": status, "metrics": metrics, "command": launch_file, "validation": binding}
    seal(directory, outcome, started)
    return {"directory": directory, "record": outcome, **read(directory / "seal.json")}


def recover_interrupted(root, protocol, rows, batch):
    raw = root / "raw"
    if not raw.exists():
        return
    for row in rows:
        case = raw / row["id"]
        if not case.exists():
            break
        entries = list(case.iterdir())
        if not entries:
            case.rmdir()
            break
        directory = entries[0]
        require(len(entries) == 1 and directory.is_dir() and not case.is_symlink() and
                not directory.is_symlink() and RUN_ID.fullmatch(directory.name), "invalid interrupted attempt identity")
        if (directory / "seal.json").is_file():
            continue
        started_file = directory / "started.json"
        pending = read(started_file) if started_file.exists() else {
            "case_id": row["id"], "run_id": directory.name, "timeout_s": row["timeout_s"],
        }
        require(pending["case_id"] == row["id"] and pending["run_id"] == directory.name and
                positive(pending["timeout_s"]) and pending["timeout_s"] <= row["timeout_s"], "interrupted attempt differs")
        record = directory / "record.json"
        if record.exists():
            previous = directory / f"interrupted-record-{uuid.uuid4().hex}.json"
            record.rename(previous)
        pending_seal = directory / "seal.pending"
        if pending_seal.exists():
            pending_seal.rename(directory / f"interrupted-seal-{uuid.uuid4().hex}.json")
        launch = next((rel for rel in ("core/launch/command.json", "launch/command.json")
                       if (directory / rel).is_file()), None)
        observed = read(directory / launch) if launch else None
        reason = "interrupted before final seal; historical evidence retained"
        status = {"run_id": directory.name, "status": "FAIL", "validation_status": "NOT_RUN",
                  "censoring": None, "reference_run_id": None, "reason": reason,
                  "exit_code": observed["exit_code"] if observed else None}
        if observed and observed["status"] == "TIMEOUT":
            status.update(status="TIMEOUT", censoring="right")
        elapsed = max(pending["timeout_s"], observed["elapsed_s_driver"] if observed else 0)
        seal(directory, {"manifest": manifest_for(protocol, row, batch["runtime"], batch["scope"], directory.name),
                         "status": status, "metrics": missing_metrics(mode_for(row), reason),
                         "command": launch, "validation": None}, perf_counter() - elapsed)
        break


def read_batch(root, protocol, rows):
    batch = read(root / "batch.json")
    runtime = batch["runtime"]
    expected_scope = scope_for(batch["stage"], protocol)
    require(batch["protocol_hash"] == protocol.identity and batch["scope"] == expected_scope and
            batch["case_ids"] == [row["id"] for row in rows] and
            batch["schedule_sha256"] == sha256(json_bytes(rows)), "batch schedule or protocol differs")
    environment = read(root / "environment.json")
    require(sha256(json_bytes(environment)) == runtime["environment_sha256"], "batch environment was altered")
    attempts = read_attempts(root)
    known = set(attempts)
    require(known == {row["id"] for row in rows[:len(known)]}, "raw attempts are not a unique schedule prefix")
    for row in rows[:len(known)]:
        item = attempts[row["id"]]
        raw = item["record"]
        expected = manifest_for(protocol, row, runtime, expected_scope, item["directory"].name)
        require(all(raw["manifest"][key] == val for key, val in expected.items()
                    if key not in ("backend_effective", "validation_run_id")) and
                raw["metrics"]["measurement_mode"] == mode_for(row), "raw schedule identity differs")
        validation = raw["validation"]
        require(raw["manifest"]["validation_run_id"] == (validation["run_id"] if validation else None),
                "raw validation identity differs")
    return batch, attempts


def claim_formal_stage(protocol, batch, root, resume):
    # The same approved protocol may not be restarted under a fresh result directory.
    directory = Path.home() / ".coreorder" / "execution" / protocol.plan["protocol_lock_hash"]
    marker = directory / f"{batch['stage']}.json"
    claim = {"output": str(root), "batch_sha256": sha256(json_bytes(batch))}
    if resume:
        require(marker.is_file() and read(marker) == claim, "formal stage owner differs")
    else:
        require(not marker.exists(), "formal stage already claimed; resume the original output directory")
        write(marker, claim)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT, help="directory with frozen.json and protocol_lock.json")
    parser.add_argument("--stage", choices=("check", "C01", "V01", "pilot", *FORMAL), required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case", action="append", default=[], help="C01/V01 case ID, repeatable")
    parser.add_argument("--receipts", type=Path, help="sealed V01 batch for formal admission")
    parser.add_argument("--budget-seconds", type=float, help="lower the frozen host budget")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--acknowledge-interrupted", action="store_true",
                        help="confirm that an interrupted attempt and all its workers have exited")
    args = parser.parse_args(argv)
    try:
        protocol = Protocol(args.plan)
        if args.stage == "check":
            print("execution authorization" if protocol.research else "G3", protocol.plan["status"], {stage: len(rows) for stage, rows in protocol.rows.items()})
            return 0
        require(args.output is not None, "--output is required for execution")
        require(not args.acknowledge_interrupted or args.resume, "interrupted recovery requires --resume")
        rows = stage_rows(protocol, args.stage, args.case)
        require(rows, "no executable rows selected")
        root = args.output.resolve()
        scope = scope_for(args.stage, protocol)
        with exclusive_host(args.acknowledge_interrupted, root):
            actual, runtime = inspect_environment(protocol, args.stage in FORMAL or any(
                row["settings"]["backend"].startswith("native") for row in rows))
            external = None
            if args.stage in FORMAL:
                require(all(value == "1" for value in actual["external_threads"].values()),
                        "formal execution requires one external BLAS/OpenMP thread")
                external = qualify_external(protocol, runtime, args.receipts.resolve() if args.receipts else None)
            frozen = protocol.plan["primary"]["max_minutes"] * 60
            budget = frozen if args.budget_seconds is None else args.budget_seconds
            require(positive(budget) and budget <= frozen, "budget must be positive and within frozen host cap")
            batch = {"format": "r4-experiment-batch-v1", "protocol_hash": protocol.identity, "stage": args.stage,
                     "scope": scope, "runtime": runtime, "selected_cases": args.case, "budget_s": budget,
                     "case_ids": [row["id"] for row in rows], "schedule_sha256": sha256(json_bytes(rows))}
            if args.resume:
                require(read(root / "batch.json") == batch, "resume identity, runtime or budget differs")
                if args.stage in FORMAL:
                    claim_formal_stage(protocol, batch, root, True)
                recover_interrupted(root, protocol, rows, batch)
                previous, attempts = read_batch(root, protocol, rows)
                require(previous == batch, "resume identity, runtime or budget differs")
            else:
                root.mkdir(parents=True, exist_ok=False)
                if args.stage in FORMAL:
                    claim_formal_stage(protocol, batch, root, False)
                write(root / "batch.json", batch)
                write(root / "environment.json", actual)
                attempts = {}
            elapsed = Counter()
            process_timeouts = set()
            for row in rows[:len(attempts)]:
                existing = attempts[row["id"]]
                phase = "E05" if row["phase"].startswith("E05-") else row["phase"]
                elapsed[phase] += existing["elapsed_s"]
                if existing["record"]["status"]["status"] == "TIMEOUT" and row["settings"]["backend"] == "py-process":
                    process_timeouts.add(row["workload"])
            for row in rows[len(attempts):]:
                phase = "E05" if row["phase"].startswith("E05-") else row["phase"]
                cap = protocol.plan["primary"]["stage_budgets_minutes"][phase] * 60
                remaining = min(cap - elapsed[phase], budget - sum(elapsed.values()))
                if remaining <= 0:
                    print(f"NOT_RUN budget exhausted before {row['id']}", file=sys.stderr)
                    break
                skip = ("prior process timeout for workload" if row["settings"]["backend"] == "py-process" and
                        row["workload"] in process_timeouts else None)
                item = attempt(protocol, row, runtime, scope, root, min(row["timeout_s"], remaining),
                               attempts, external, skip_reason=skip)
                attempts[row["id"]] = item
                result = item["record"]["status"]["status"]
                if result == "TIMEOUT" and row["settings"]["backend"] == "py-process":
                    process_timeouts.add(row["workload"])
                elapsed[phase] += item["elapsed_s"]
                print(row["id"], result, item["directory"].name, flush=True)
                require(not HOST_LEASE.exists(), f"process tree cleanup unconfirmed: {item['directory']}")
            counts = Counter(item["record"]["status"]["status"] for item in attempts.values())
            counts["NOT_RUN"] += len(rows) - len(attempts)
            print(scope, dict(counts))
            return 0 if counts["PASS"] == len(rows) else 1
    except (ValueError, KeyError, TypeError, OSError, ValidationError, NotImplementedError, subprocess.SubprocessError) as error:
        print(f"experiment refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
