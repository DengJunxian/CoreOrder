"""Package a reviewed candidate and actual receipts without issuing team signoffs."""
from argparse import ArgumentParser
from pathlib import Path
import shutil

from experiments.protocol import Protocol, file_hash
from validation.io import read, write


def assemble(staged, output, c01_index, v01_index, calibration, replay_receipt):
    candidate = Protocol(staged)
    plan, lock = candidate.plan, candidate.lock
    assert not candidate.active and plan["authorized_formal_runs"] == []
    assert c01_index["stage"] == "C01" and c01_index["planned_candidates"] == 360
    assert v01_index["stage"] == "V01" and v01_index["protocol_hash"] == candidate.identity
    runtime = c01_index["runtime"]
    assert runtime == v01_index["runtime"] and runtime["dirty"] is False
    assert runtime["git_sha"] == lock["primary_x86"]["code_sha"]
    accepted = v01_index["accepted"]
    assert len(accepted) <= plan["V01_candidate_receipts_required"]
    shutil.copytree(staged, output, ignore=shutil.ignore_patterns("frozen.json", "protocol_lock.json"))
    phase_batches = {}
    for index in (c01_index, v01_index):
        state = "PASS" if sum(index["census"].values()) == index["census"].get("PASS", 0) else "BLOCKED"
        phase = index["stage"]
        phase_batches[phase] = {"status": state, "batch_sha256": index["batch_digest"],
                                "protocol_hash": index["protocol_hash"], "schedule_sha256": index["schedule_digest"],
                                "census": index["census"], "raw_root": index["raw_root"]}
        next(item for item in plan["stages"] if item["id"] == phase)["status"] = state

    accepted_ids = {item["run_id"] for item in accepted.values()}
    diag = plan["diagnostics"]["replay"]
    if calibration and replay_receipt:
        samples = read(calibration)
        expected = {(size, backend, layout) for size in diag["rows"] for layout in diag["layouts"]
                    for backend in ("native-serial", "native-parallel")}
        assert len(samples) == len(expected) and {(item["rows"], item["backend"], item["layout"])
                                                for item in samples} == expected
        assert all(item["native_sha256"] == runtime["native_sha256"] for item in samples)
        repeats, = {item["repeats"] for item in samples}
        receipt = read(replay_receipt)
        source = diag["source"]
        selected = next(item for item in v01_index["records"] if item.get("run_id") == receipt["validation_run_id"])
        assert receipt["validation_run_id"] in accepted_ids and selected["status"] == "PASS"
        assert selected["settings"] == source["mode"] == receipt["source_settings"]
        assert selected["seed"] == source["seed"] == receipt["seed"]
        assert selected["receipt"]["production_final"] == receipt["production_final"]
        assert receipt["git_sha"] == runtime["git_sha"] and receipt["native_sha256"] == runtime["native_sha256"]
        assert receipt["host_id"] == runtime["host_id"]
        raw = replay_receipt.parent / receipt["path"]
        assert file_hash(raw) == receipt["capture_sha256"]
        stash = output / "replay-source"
        stash.mkdir()
        shutil.copyfile(raw, stash / "input.aos")
        record = stash / "capture-receipt.json"
        write(record, {**receipt, "path": "replay-source/input.aos"})
        source.update(input_sha256=receipt["input_sha256"],
                      receipt={"path": record.relative_to(output).as_posix(), "sha256": file_hash(record)})
        diag.update(kernel_repeat_count=repeats,
                    kernel_repeats_reason="seed 11 x86 calibration on the same binary; fixed across layouts/backend",
                    calibration_s={"min": min(item["replay_s"] for item in samples),
                                   "max": max(item["replay_s"] for item in samples)})
    reasons = ["team signoffs on the exact version remain outstanding"]
    if len(accepted) != plan["V01_candidate_receipts_required"]:
        reasons.insert(0, "V01 validation is incomplete")
    if phase_batches["C01"]["status"] != "PASS":
        reasons.insert(0, "C01 validation is incomplete")
    if not diag["source"]["receipt"]:
        reasons.append("E05 capture and calibration not qualified")
    plan.update(reason="; ".join(reasons), hash_receipt="configs/experiments/r4b/R4B-SHA256SUMS",
                V01_candidate_receipts_accepted=len(accepted))
    lock.update(correctness_batches=phase_batches)
    lock["approval"].update(V01_accepted=len(accepted), V01_receipts=accepted)
    assert plan["formal_code_sha"] is None and plan["protocol_lock_hash"] is None
    assert lock["approval"]["A_signoff"] is None and lock["approval"]["E_signoff"] is None
    write(output / "frozen.json", plan)
    lock["candidate_files_sha256"] = {p.relative_to(output).as_posix(): file_hash(p)
                                       for p in sorted(output.rglob("*")) if p.is_file()}
    write(output / "protocol_lock.json", lock)
    with (output / "R4B-SHA256SUMS").open("x", encoding="utf8") as file:
        for p in sorted(output.rglob("*")):
            if p.is_file() and p.name != "R4B-SHA256SUMS":
                file.write(f"{file_hash(p)}  {p.relative_to(output).as_posix()}\n")
    check = Protocol(output)
    assert not check.active
    assert all(candidate.rows[key] == check.rows[key] for key in candidate.rows)
    print("BLOCKED", check.identity, phase_batches)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    for name in ("staged", "output", "c01_index", "v01_index"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--replay-receipt", type=Path)
    opts = parser.parse_args()
    assemble(opts.staged, opts.output, read(opts.c01_index), read(opts.v01_index),
             opts.calibration, opts.replay_receipt)
