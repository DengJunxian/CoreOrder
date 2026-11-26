"""Compare proposed orders before PAMS tick rounding on real runner entry points."""

import random
import subprocess
import sys
from pathlib import Path

from audit_p10 import INPUT_SHA, ROOT, execute
from validation.codec import encode
from validation.compare import first_diff
from validation.io import read, write
from validation.upstream import load


def observe(config, seed, output, mode, restore="upstream", layout="not_applicable", workers="1"):
    if mode == "oracle":
        load(ROOT / "vendor/pams")
    from pams.runners.sequential import SequentialRunner

    checks = SequentialRunner._check_submitted_orders.__code__
    handles = SequentialRunner._handle_orders.__code__
    seen = {"checks": [], "handles": []}

    def profile(frame, event, value):
        if event != "call":
            return
        local = frame.f_locals
        if frame.f_code == checks:
            seen["checks"].append([local["agent"].agent_id, encode(local["orders"])])
        elif frame.f_code == handles:
            seen["handles"].append([local["session"].session_id, encode(local["local_orders"])])

    if mode == "oracle":
        runner = SequentialRunner(settings=config, prng=random.Random(seed))
        run = runner.main
    else:
        from coreorder.cli import main

        def run():
            args = ["run", "--backend", mode, "--book-restore", restore, "--workers", workers,
                    "--config", str(config), "--seed", str(seed), "--output", str(output / "run")]
            if layout != "not_applicable":
                args.extend(("--layout", layout))
            if mode == "native-parallel":
                args.extend(("--grain", "2", "--schedule", "dynamic"))
            assert main(args) == 0

    sys.setprofile(profile)
    try:
        run()
    finally:
        sys.setprofile(None)
    write(output / "orders-before-tick-rounding.json.gz", seen)


def run(output):
    subprocess.run(["git", "diff", "--exit-code", INPUT_SHA, "HEAD", "--", "src", "native", "vendor",
                    "validation", "include", "configs", "schemas", "CMakeLists.txt"], check=True)
    output.mkdir()
    count = 0
    for name in ("smoke", "native-serial-normal"):
        config = ROOT / "configs/workloads" / f"{name}.json"
        target = output / name
        target.mkdir()
        source = target / "oracle"
        source.mkdir()
        assert execute(source / "command", (__file__, "observe", config, 42, source, "oracle")) == 0
        expected = read(source / "orders-before-tick-rounding.json.gz")
        cases = [("py-seq", "incremental", "not_applicable", "1"),
                 ("py-thread", "incremental", "not_applicable", "2"),
                 ("py-process", "upstream", "not_applicable", "2")]
        cases.extend((backend, restore, layout, workers)
                     for (backend, workers) in (("native-serial", "1"), ("native-parallel", "4"))
                     for restore in ("upstream", "incremental") for layout in ("aos", "soa"))
        for case in cases:
            candidate = target / "-".join(case)
            candidate.mkdir()
            code = execute(candidate / "command", (__file__, "observe", config, 42, candidate, *case))
            assert code == 0, candidate / "command/stderr.log"
            actual = read(candidate / "orders-before-tick-rounding.json.gz")
            diff = first_diff(expected, actual)
            records = {"config": str(config), "seed": 42, "status": "FAIL" if diff else "PASS",
                       "difference": diff, "checked_groups": len(expected["checks"]),
                       "handle_calls": len(expected["handles"])}
            write(candidate / "comparison.json", records)
            assert diff is None, records
            count += 1
        print(name, "PASS", len(cases), len(expected["checks"]), len(expected["handles"]), flush=True)
    print(f"PASS {count} production executions matched raw Order identity, TTL, side and floating-point prices.", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "observe":
        observe(Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]), *sys.argv[5:])
    else:
        run(Path(sys.argv[1]).resolve())
