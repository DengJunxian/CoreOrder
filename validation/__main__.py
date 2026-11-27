"""Standalone CLI until A registers coreorder validate. SPDX-License-Identifier: EPL-1.0."""
import argparse
import json
from pathlib import Path

from .io import read, write


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("collect")
    run.add_argument("--config", required=True)
    run.add_argument("--pams-root", default="vendor/pams")
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--backend", choices=("py-seq", "py-thread", "py-process"), default="py-seq")
    run.add_argument("--workers", type=int, default=2)
    run.add_argument("--output", required=True)
    run.add_argument("--stream", action="store_true")
    diff = commands.add_parser("compare")
    diff.add_argument("--reference", required=True)
    diff.add_argument("--candidate", required=True)
    diff.add_argument("--bundle")
    diff.add_argument("--stream", action="store_true")
    replay = commands.add_parser("replay")
    replay.add_argument("--bundle", required=True)
    args = parser.parse_args()
    if args.command == "collect":
        if args.workers < 1 or args.seed < 0:
            parser.error("workers must be positive and seed nonnegative")
        from .reference import collect
        result = collect(read(args.config), args.seed, args.pams_root, args.backend, args.workers,
                         stream_path=args.output if args.stream else None)
        if args.stream:
            print(json.dumps({k: result[k] for k in ("backend_effective", "events", "steps")}))
            return 0
        write(args.output, result)
        print(json.dumps({"backend_effective": result["backend_effective"], "hashes": result["hashes"],
                          "events": len(result["events"]), "steps": len(result["steps"])}))
        return 0
    if getattr(args, "stream", False):
        from .stream import compare_streams, save_difference
        report = compare_streams(args.reference, args.candidate)
        if report["status"] != "PASS" and args.bundle:
            save_difference(report, args.reference, args.candidate, args.bundle)
        print(json.dumps(report))
        return int(report["status"] != "PASS")
    from .compare import compare, save_reproducer
    if args.command == "replay":
        root = Path(args.bundle)
        reference, candidate = read(root / "reference.json.gz"), read(root / "candidate.json.gz")
    else:
        reference, candidate = read(args.reference), read(args.candidate)
    report = compare(reference, candidate)
    if args.command == "compare" and args.bundle and report["status"] == "FAIL":
        save_reproducer(reference, candidate, args.bundle, args.reference, args.candidate)
    print(json.dumps({k: v for k, v in report.items() if k not in ("context", "rng_context")}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
