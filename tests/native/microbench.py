"""Measure serial binding calls over replayed public FCN rows (module diagnostic)."""

import hashlib
import json
import platform
import statistics
import sys
import time

import numpy as np

import _coreorder_fcn
from fcn_cases import columns, public_replay


def main():
    fixture, _ = public_replay()
    evaluator = _coreorder_fcn.Evaluator()
    results = []
    for repeat in (1, 17, 171):
        rows = np.tile(fixture, repeat)
        soa = columns(rows)
        output = evaluator.aos(rows).tobytes()
        if evaluator.soa(soa).tobytes() != output:
            raise RuntimeError("layout outputs differ on benchmark inputs")
        per_block = {"aos": [], "soa": []}
        modes = [("aos", evaluator.aos, rows), ("soa", evaluator.soa, soa)]
        calls = 300
        for block in range(7):
            for layout, compute, data in (modes if block % 2 == 0 else modes[::-1]):
                for _ in range(20):
                    compute(data)
                started = time.perf_counter_ns()
                for _ in range(calls):
                    compute(data)
                per_block[layout].append(time.perf_counter_ns() - started)
        results.append({
            "rows": len(rows), "input_bytes": rows.nbytes, "output_bytes": len(output),
            "input_sha256": hashlib.sha256(rows.tobytes()).hexdigest(),
            "output_sha256": hashlib.sha256(output).hexdigest(), "calls_per_block": calls,
            "block_ns": per_block,
            "median_ns_per_call": {mode: statistics.median(times) / calls for mode, times in per_block.items()},
        })
    print(json.dumps({
        "scope": "Module diagnostic, hot serial binding over tiled 24 public fixture rows",
        "included": "validation, result allocation, arithmetic, error scan, binding call",
        "excluded": "packing, RNG, Order construction, Taskflow and full simulation",
        "platform": platform.platform(), "python": sys.version,
        "numpy": np.__version__, "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()
