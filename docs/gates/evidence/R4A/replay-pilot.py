"""Capture actual packed AoS calls through an explicit diagnostic wrapper, then replay their prefixes."""
from functools import wraps
from pathlib import Path
import json
import sys

from coreorder.cli import main
from coreorder.native_serial import NativeSerialRunner
from coreorder.packing import INPUT_DTYPE, OUTPUT_DTYPE
from experiments.capture import execute
from experiments.protocol import file_hash
from validation.io import read, write

ROOT = Path(sys.argv[1]).resolve()
CONFIG = "configs/experiments/workloads/W2-H.json"


def capture():
    output = ROOT / "capture"
    output.mkdir(parents=True, exist_ok=False)
    original = NativeSerialRunner.__init__
    raw = output / "input.aos"
    rows = 0
    with raw.open("xb") as stream:
        def observed_initialization(self, *args, evaluate, **kwargs):
            @wraps(evaluate)
            def observed(inputs):
                nonlocal rows
                assert inputs.dtype == INPUT_DTYPE
                selected = inputs[:8192 - rows]
                stream.write(selected.tobytes())
                rows += len(selected)
                return evaluate(inputs)

            original(self, *args, evaluate=observed, **kwargs)

        NativeSerialRunner.__init__ = observed_initialization
        try:
            exit_code = main(["run", "--mode", "profile", "--cprofile", "--_measurement-child",
                              "--backend", "native-serial", "--seed", "11", "--layout", "aos",
                              "--config", CONFIG, "--book-restore", "incremental", "--output", str(output)])
        finally:
            NativeSerialRunner.__init__ = original

    metrics = read(output / "metrics.json")
    if exit_code or not (rows == 8192 and metrics["native_rows"] >= rows):
        raise SystemExit(exit_code or 1)
    env = read(output / "environment.json")
    manifest = read(output / "manifest.json")
    write(output / "capture.json", {"scope": "P01 real ordered rows; instrumented production native serial",
                                    "rows": rows, "input_stride": INPUT_DTYPE.itemsize,
                                    "output_stride": OUTPUT_DTYPE.itemsize, "byteorder": sys.byteorder,
                                    "config_sha256": file_hash(Path(CONFIG)), "sha256": file_hash(raw),
                                    "native_sha256": env["native_module"]["sha256"], "git_sha": manifest["git_sha"],
                                    "run_id": manifest["run_id"], "seed": 11})


def replay():
    launcher = [sys.executable, str(Path(__file__).resolve()), str(ROOT)]
    if execute([*launcher, "capture"], ROOT / "capture-driver", 30, scope="R4A real input capture")["status"] != "PASS":
        raise SystemExit(1)
    meta = read(ROOT / "capture/capture.json")
    source = ROOT / "capture/input.aos"
    assert source.stat().st_size == meta["rows"] * meta["input_stride"]
    assert file_hash(source) == meta["sha256"]
    results = []
    for rows in (128, 512, 2048, 8192):
        repeats = max(500, 2_000_000 // rows)
        pair = []
        for layout in ("aos", "soa"):
            directory = ROOT / f"replay-{rows}-{layout}"
            report = directory / "replay.json"
            command = [sys.executable, "-m", "experiments.replay", "--input", str(source), "--sha256", meta["sha256"],
                       "--rows", str(rows), "--repeats", str(repeats), "--layout", layout,
                       "--workers", "1", "--grain", "128", "--schedule", "static",
                       "--backend", "native-serial", "--output", str(report)]
            launch = execute(command, directory / "driver", 15, scope="R4A real-input diagnostic replay")
            if launch["status"] != "PASS":
                raise SystemExit(1)
            run = read(report)
            assert run["native_sha256"] == meta["native_sha256"]
            pair.append(run["output_sha256"])
            results.append({**run, "elapsed_s_driver": launch["elapsed_s_driver"]})
        assert pair[0] == pair[1]
    write(ROOT / "summary.json", results)
    print(json.dumps(results))


if len(sys.argv) > 2:
    capture()
else:
    replay()
