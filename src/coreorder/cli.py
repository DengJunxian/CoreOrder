import argparse
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
    run.add_argument("--validation-trace", action="store_true", help="capture E semantic validation trace")

    env = commands.add_parser("environment", help="write the checkout and runtime environment")
    env.add_argument("--output", type=Path, required=True)

    validate = commands.add_parser("validate", help="invoke the independent validator")
    validate.add_argument("--suite", choices=("smoke", "g0", "g2"), required=True)
    validate.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "run":
        diagnostics = None
        if args.heap_diagnostics or args.count_heap_comparisons:
            diagnostics = HeapDiagnostics(sizes=args.heap_diagnostics, comparisons=args.count_heap_comparisons)
        execute = partial(run_py_seq, book_restore=args.book_restore, heap_diagnostics=diagnostics)
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
