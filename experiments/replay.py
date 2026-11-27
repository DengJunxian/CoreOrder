"""Replay signed, real FCN inputs through the loaded production binding."""

import argparse
import sys
from pathlib import Path
from time import perf_counter

import numpy as np

from coreorder.config import sha256
from coreorder.native_serial import load_native_serial
from coreorder.packing import INPUT_DTYPE
from validation.io import read, write

from .protocol import file_hash, require, within


def replay_command(protocol, row, directory, external):
    replay = protocol.plan["diagnostics"]["replay"]
    source = replay["source"]
    qualified = source["receipt"]
    repeats = replay["kernel_repeat_count"]
    require(isinstance(qualified, dict) and type(repeats) is int and repeats > 0,
            "E05 replay requires a qualified real capture and calibrated repeat count")
    metadata = within(protocol.directory, qualified["path"])
    require(file_hash(metadata) == qualified["sha256"], "capture receipt digest differs")
    receipt = read(metadata)
    raw = within(protocol.directory, receipt["path"])
    target = protocol.lock["primary_x86"]
    require(external is not None and any(
        entry["run_id"] == receipt["validation_run_id"] and
        entry["identity"]["seed"] == source["seed"] and
        entry["identity"]["input_hash"] == source["input_sha256"] and
        all(entry["identity"][key] == value for key, value in source["mode"].items())
        for entry, _ in external.values()
    ), "captured rows have no approved source validation")
    require(receipt["scope"] == "real production FCN rows in original order" and
            receipt["input_sha256"] == source["input_sha256"] ==
            protocol.workloads[source["workload"]]["input_sha256"] and
            receipt["seed"] == source["seed"] and receipt["git_sha"] == target["code_sha"] and
            receipt["source_settings"] == source["mode"] and receipt["host_id"] == target["host_id"] and
            receipt["native_sha256"] == target["native_module"]["sha256"] and
            receipt["stride"] == INPUT_DTYPE.itemsize and sys.byteorder == receipt["byteorder"] and
            receipt["rows"] >= row["rows"] and raw.stat().st_size == receipt["rows"] * INPUT_DTYPE.itemsize and
            file_hash(raw) == receipt["capture_sha256"], "real capture identity differs")
    setting = row["settings"]
    return [sys.executable, "-m", "experiments.replay", "--input", str(raw), "--sha256", receipt["capture_sha256"],
            "--rows", str(row["rows"]), "--repeats", str(repeats), "--layout", setting["layout"],
            "--workers", str(setting["workers"]), "--grain", str(setting["grain"] or 128),
            "--schedule", setting["schedule"] or "static", "--backend", setting["backend"],
            "--output", str(directory / "replay.json")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("input", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    for name in ("rows", "repeats", "workers", "grain"):
        parser.add_argument(f"--{name}", type=int, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--backend", choices=("native-serial", "native-parallel"), required=True)
    parser.add_argument("--layout", choices=("aos", "soa"), required=True)
    parser.add_argument("--schedule", choices=("static", "dynamic"), required=True)
    args = parser.parse_args()
    require(min(args.rows, args.repeats, args.workers, args.grain) > 0, "invalid replay dimensions")
    require(file_hash(args.input) == args.sha256, "captured input digest differs")
    rows = np.fromfile(args.input, dtype=INPUT_DTYPE, count=args.rows)
    require(len(rows) == args.rows, "capture has too few rows")
    payload = rows if args.layout == "aos" else {name: rows[name].copy() for name in INPUT_DTYPE.names}
    module = load_native_serial()
    before = module.executor_creations()
    evaluator = module.Evaluator(parallel=args.backend == "native-parallel", workers=args.workers,
                                 grain=args.grain, schedule=args.schedule)
    evaluate = getattr(evaluator, args.layout)
    start = perf_counter()
    for _ in range(args.repeats):
        output = evaluate(payload)
    elapsed = perf_counter() - start
    write(args.output, {
        "measurement_scope": "production native binding, allocation and executor wait on captured inputs",
        "replay_s": elapsed, "rows": args.rows, "repeats": args.repeats,
        "replay_row_evaluations": args.rows * args.repeats,
        "capture_sha256": args.sha256, "output_sha256": sha256(output.tobytes()),
        "native_sha256": file_hash(Path(module.__file__).resolve()), "backend": args.backend, "layout": args.layout,
        "workers": args.workers, "native_executor_creations": module.executor_creations() - before,
    })


if __name__ == "__main__":
    main()
