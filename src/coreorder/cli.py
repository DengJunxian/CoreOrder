import argparse
import math
import re
import subprocess
import sys
from functools import partial
from pathlib import Path

from jsonschema import ValidationError

from .config import json_bytes
from .environment import environment
from .heap_diagnostics import HeapDiagnostics
from .run_records import run_recorded
from .runner import run_py_seq
from .schema import validate_record
from .validate import run_validation


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="python -m coreorder")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="run a PAMS workload")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--seed", type=int, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument(
        "--backend",
        choices=("py-seq", "py-thread", "py-process", "native-serial", "native-parallel"),
        default="py-seq",
    )
    run.add_argument("--book-restore", choices=("upstream", "incremental"), default="upstream")
    run.add_argument("--heap-diagnostics", action="store_true", help="record per-side restoration sizes")
    run.add_argument("--count-heap-comparisons", action="store_true", help="count Order comparisons during restoration")
    run.add_argument("--workers", type=int, default=1)
    run.add_argument("--layout", choices=("aos", "soa"))
    run.add_argument("--grain", type=int)
    run.add_argument("--schedule", choices=("static", "dynamic"))
    run.add_argument("--stream-validation", action="store_true", help="lossless bounded-memory validation trace")
    run.add_argument("--validation-trace", action="store_true", help="capture E semantic validation trace")
    run.add_argument("--mode", choices=("validation", "timing", "profile", "pmu"),
                     help="select an observation mode (default preserves legacy diagnostics)")
    run.add_argument("--cprofile", action="store_true", help="in profile mode, collect full cProfile instead of spans")
    run.add_argument("--pmu-event", action="append", default=[], help="Linux perf event, repeatable in pmu mode")
    run.add_argument("--timeout", type=float, default=30, help="single explicit run deadline in seconds")
    run.add_argument("--_measurement-child", action="store_true", help=argparse.SUPPRESS)
    run.add_argument("--_run-id", help=argparse.SUPPRESS)
    run.add_argument("--reference-trace", type=Path, help="reuse a verified PAMS trace in validation mode")

    env = commands.add_parser("environment", help="write the checkout and runtime environment")
    env.add_argument("--output", type=Path, required=True)

    validate = commands.add_parser("validate", help="invoke the independent validator")
    validate.add_argument("--suite", choices=("smoke", "g0", "g1", "g2"), required=True)
    validate.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "run":
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            run.error("--timeout must be finite and positive")
        if args.mode in ("timing", "profile", "pmu") and (
            args.validation_trace or args.heap_diagnostics or args.count_heap_comparisons
        ):
            run.error("trace and heap diagnostics require validation or legacy diagnostics")
        if args.cprofile and args.mode != "profile":
            run.error("--cprofile requires --mode profile")
        if (args.mode == "pmu") != bool(args.pmu_event):
            run.error("--mode pmu requires explicit --pmu-event values")
        if args._run_id and not re.fullmatch(r"[0-9a-f]{32}", args._run_id):
            run.error("invalid run identity")
        if args.stream_validation and args.mode != "validation":
            run.error("--stream-validation requires --mode validation")
        if args.reference_trace is not None and args.mode != "validation":
            run.error("--reference-trace requires --mode validation")
        if args.mode is not None and not args._measurement_child:
            from .measurement import launch_measurement
            return launch_measurement(args, argv)
        diagnostics = None
        if args.heap_diagnostics or args.count_heap_comparisons:
            diagnostics = HeapDiagnostics(sizes=args.heap_diagnostics, comparisons=args.count_heap_comparisons)
        execute = partial(run_py_seq, book_restore=args.book_restore, heap_diagnostics=diagnostics,
                          close_native=args.mode is not None)
        return run_recorded(args, execute, entry_point="coreorder", heap_diagnostics=diagnostics)

    if args.command == "validate":
        return run_validation(args)

    try:
        record = environment()
        validate_record("environment", record)
        data = json_bytes(record)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as output:
            output.write(data)
    except (OSError, ValueError, ValidationError, subprocess.CalledProcessError) as error:
        print(f"cannot write environment: {error}", file=sys.stderr)
        return 1
    print(args.output)
    return 0
