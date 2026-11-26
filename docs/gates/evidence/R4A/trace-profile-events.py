"""Identify the CPython profile callback object on a real C01b production batch."""
from collections import Counter
from pathlib import Path
import sys

from coreorder.cli import main
from coreorder.native_serial import NativeSerialRunner
from coreorder.phase_profile import PhaseProfile

counts = Counter()
batch = NativeSerialRunner._evaluate_batch.__code__
observe = PhaseProfile.observe


def diagnostic(self, frame, event, arg):
    if frame.f_code is batch and event in ("c_call", "c_return"):
        evaluate = frame.f_locals["self"]._evaluate
        func = getattr(evaluate, "__func__", evaluate)
        if getattr(arg, "__name__", None) == evaluate.__name__:
            counts[(event, type(arg).__name__, arg is func, arg == func,
                    getattr(arg, "__self__", None) is getattr(func, "__self__", None))] += 1
    return observe(self, frame, event, arg)


PhaseProfile.observe = diagnostic
output = Path(sys.argv[1]).resolve()
output.mkdir()
code = main(["run", "--mode", "profile", "--_measurement-child", "--config",
             "configs/experiments/workloads/c01/C01b-normal.json", "--seed", "11", "--output",
             str(output), "--book-restore", "incremental", "--backend", "native-serial",
             "--layout", "aos"])
for event, count in counts.items():
    print("event, callback type, same object, rich equality, same receiver =", event, "count =", count)
raise SystemExit(code)
