"""Pair the P11 plain Logger with the R2A counter Logger on one small PAMS workload."""

import json
import sys
import warnings
from functools import partial
from pathlib import Path
from statistics import median

from pams.logs import Logger

from coreorder.config import ROOT, incremental_workload, json_bytes, load_workload, sha256
from coreorder.environment import environment
from coreorder.market_adapter import CoreOrderMarket
from coreorder.native_serial import NativeSerialRunner, load_native_serial
from coreorder.runner import run_py_seq
from coreorder.snapshot import WorkloadCounts, final_rng, final_state


def main(output):
    output.mkdir(exist_ok=False)
    config = ROOT / "vendor/pams/samples/CI2002/config.json"
    raw = config.read_bytes()
    incremental = output / "incremental.json"
    incremental.write_bytes(json_bytes(incremental_workload(load_workload(raw))))
    module = load_native_serial()

    def native_factory(**kwargs):
        evaluator = module.Evaluator(parallel=True, workers=2)
        return NativeSerialRunner(evaluate=evaluator.soa, layout="soa", record_batch_widths=False,
                                  market_adapter=CoreOrderMarket, **kwargs)

    rows = []
    for backend, restore, path, options in (
        ("py-seq", "upstream", config, {}),
        ("py-seq", "incremental", incremental, {}),
        ("native-parallel/soa/w2", "incremental", incremental, {"runner_factory": native_factory}),
    ):
        pairs = []
        fingerprints = set()
        workload_counts = []
        for repeat in range(8):
            pair = {}
            variants = (("plain", Logger), ("counts", WorkloadCounts))
            for name, logger_type in (variants if repeat % 2 == 0 else reversed(variants)):
                observer = logger_type()
                runner, timing = run_py_seq(path, 11, observer, book_restore=restore, close_native=True, **options)
                fingerprints.add((sha256(json_bytes(final_state(runner.simulator))),
                                  sha256(json_bytes(final_rng(runner)))))
                pair[name] = timing["simulation_s"]
                if name == "counts":
                    workload_counts.append((observer.counts, observer.market_steps))
            pairs.append(pair)
        assert len(fingerprints) == 1 and all(row == workload_counts[0] for row in workload_counts)
        state_hash, rng_hash = next(iter(fingerprints))
        ratios = [pair["counts"] / pair["plain"] for pair in pairs]
        rows.append({
            "backend": backend, "book_restore": restore, "first_variant": "plain",
            "pairs_s": pairs, "median_ratio": median(ratios), "min_ratio": min(ratios), "max_ratio": max(ratios),
            "counts": workload_counts[0][0], "market_steps": workload_counts[0][1],
            "final_state_sha256": state_hash, "final_rng_sha256": rng_hash,
        })
    env = environment()
    result = {"scope": "development logger comparison", "seed": 11, "workload_sha256": sha256(raw),
              "native_sha256": sha256(Path(module.__file__).read_bytes()), "environment": env, "rows": rows}
    (output / "logger-probe.json").write_bytes(json_bytes(result))
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    # Keep terminal warning handling outside this isolated Logger comparison.
    warnings.filterwarnings("ignore", message="order price does not accord to the tick size")
    main(Path(sys.argv[1]))
