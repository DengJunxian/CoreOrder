"""Capture real W2 inputs for qualification and bind final capture to a sealed V01 receipt."""
from argparse import ArgumentParser
from contextlib import contextmanager
from functools import wraps
import os
from pathlib import Path
import sys

from coreorder.cli import main as coreorder
from coreorder.native_serial import NativeSerialRunner
from coreorder.packing import INPUT_DTYPE
from experiments.capture import execute
from experiments.evidence import inspect_environment, read_attempts, validation_binding
from experiments.protocol import Protocol, condition, file_hash, is_oracle
from experiments.run import exclusive_host
from validation.io import read, write

LIMIT = 8192


@contextmanager
def observe(stream):
    init = NativeSerialRunner.__init__
    rows = 0

    def observed_init(self, *, evaluate, **options):
        @wraps(evaluate)
        def observed(inputs):
            nonlocal rows
            assert inputs.dtype == INPUT_DTYPE
            if rows < LIMIT:
                data = inputs[:LIMIT - rows]
                stream.write(data.tobytes())
                rows += len(data)
            return evaluate(inputs)
        init(self, evaluate=observed, **options)

    NativeSerialRunner.__init__ = observed_init
    try:
        yield
        if rows != LIMIT:
            raise ValueError(f"required {LIMIT} rows in original order; found {rows}")
    finally:
        NativeSerialRunner.__init__ = init


def child(args, protocol, config, source):
    out = args.output / "core"
    out.mkdir()
    raw = args.output / "input.aos"
    with raw.open("xb") as stream, observe(stream):
        code = coreorder(["run", "--mode", "profile", "--cprofile", "--_measurement-child", "--seed", str(args.seed),
                          "--config", str(config["file"]), "--output", str(out), "--backend", "native-serial",
                          "--book-restore", "incremental", "--layout", "aos", "--workers", "1"])
        if code:
            raise SystemExit(code)
    assert raw.stat().st_size == LIMIT * INPUT_DTYPE.itemsize
    native = read(out / "environment.json")["native_module"]
    manifest = read(out / "manifest.json")
    status = read(out / "status.json")
    timing = read(out / "metrics.json")
    assert status["status"] == "PASS" and timing["native_rows"] >= LIMIT
    assert manifest["backend_effective"] == "native-serial" and manifest["input_hash"] == config["input_sha256"]
    write(args.output / "capture-observed.json", {
        "scope": "real production FCN rows in original order",
        "path": raw.name, "rows": LIMIT, "stride": INPUT_DTYPE.itemsize, "byteorder": sys.byteorder,
        "capture_sha256": file_hash(raw), "input_sha256": config["input_sha256"], "seed": args.seed,
        "source_settings": source["mode"], "host_id": manifest["host_id"], "native_sha256": native["sha256"],
        "git_sha": manifest["git_sha"], "profile_run_id": manifest["run_id"],
        "production_final": {k: status[k] for k in ("final_state_hash", "rng_hash")},
    })


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--v01", type=Path)
    parser.add_argument("--calibrate", type=int)
    parser.add_argument("--child", action="store_true")
    args = parser.parse_args()
    args.output = args.output.resolve()
    protocol = Protocol(args.plan)
    replay = protocol.plan["diagnostics"]["replay"]
    source = replay["source"]
    config = protocol.workloads[source["workload"]]
    if args.child:
        child(args, protocol, config, source)
        return

    if args.calibrate:
        assert not args.v01 and args.seed in protocol.plan["pilot_seeds"]
    else:
        assert args.v01 and args.seed == source["seed"]
    args.output.mkdir()
    with exclusive_host(False, args.output):
        _, runtime = inspect_environment(protocol, native=True)
        target = protocol.lock["primary_x86"]
        assert runtime["dirty"] is False and runtime["git_sha"] == target["code_sha"]
        assert runtime["native_sha256"] == target["native_module"]["sha256"]
        assert runtime["host_id"] == target["host_id"] and runtime["environment_sha256"] == target["environment_sha256"]
        assert sorted(os.sched_getaffinity(0)) == target["affinity"]["guest_cpus"]
        receipt = None
        if args.v01:
            row = next(item for item in protocol.rows["V01"] if not is_oracle(item) and
                       item["workload"] == source["workload"] and item["seed"] == args.seed and
                       item["settings"] == source["mode"])
            attempts = read_attempts(args.v01)
            receipt, _ = validation_binding(attempts[row["id"]], condition(config, row, runtime), attempts)
        launch = execute([sys.executable, __file__, *sys.argv[1:], "--child"],
                         args.output / "capture-launch", 45, scope="R4B independent replay capture")
        if launch["status"] != "PASS":
            raise SystemExit(1)
        captured = read(args.output / "capture-observed.json")
        if receipt is not None:
            assert captured["production_final"] == receipt["production_final"]
            write(args.output / "capture-receipt.json", {**captured, "validation_run_id": receipt["run_id"]})
            return
        results = []
        for size in replay["rows"]:
            for backend, workers in (("native-serial", 1), ("native-parallel", 4)):
                pair = []
                for layout in replay["layouts"]:
                    directory = args.output / f"{size}-{backend}-{layout}"
                    path = directory / "replay.json"
                    command = [sys.executable, "-m", "experiments.replay",
                               "--input", str(args.output / captured["path"]), "--sha256", captured["capture_sha256"],
                               "--rows", str(size), "--repeats", str(args.calibrate), "--workers", str(workers),
                               "--grain", "128", "--schedule", "static", "--backend", backend, "--layout", layout,
                               "--output", str(path)]
                    result = execute(command, directory / "launch", 15, scope="R4B seed-11 replay calibration")
                    if result["status"] != "PASS":
                        raise SystemExit(1)
                    output = read(path)
                    assert output["native_sha256"] == runtime["native_sha256"]
                    pair.append(output["output_sha256"])
                    results.append(output)
                    print(size, backend, layout, f'{output["replay_s"]:.3f}s', flush=True)
                assert len(set(pair)) == 1
        write(args.output / "calibration-summary.json", results)


if __name__ == "__main__":
    main()
