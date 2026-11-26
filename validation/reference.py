"""Independent oracle API; no coreorder/native/packing imports.

SPDX-License-Identifier: EPL-1.0
"""
import copy
import random

from . import CONTRACT, PAMS_SHA
from .codec import digest, snapshot


def collect(config, seed, pams_root, backend="py-seq", workers=2):
    from .upstream import load
    load(pams_root)
    from pams.runners import SequentialRunner, MultiThreadAgentParallelRunner, MultiProcessAgentParallelRunner
    from .collector import ObservedSimulator, TraceLogger
    classes = {"py-seq": SequentialRunner, "py-thread": MultiThreadAgentParallelRunner,
               "py-process": MultiProcessAgentParallelRunner}
    if backend not in classes:
        raise ValueError("Reference supports only actual unchanged upstream runners")
    effective = copy.deepcopy(config)
    if backend != "py-seq":
        effective["simulation"]["numParallel"] = workers
        effective["simulation"]["startMethod"] = "spawn"
    logger = TraceLogger()
    runner = classes[backend](settings=effective, prng=random.Random(seed), logger=logger,
                              simulator_class=ObservedSimulator)
    logger.runner_rng = runner._prng
    runner._setup()
    initial = snapshot(runner.simulator, runner._prng)
    runner._run()
    logger._process()
    final = snapshot(runner.simulator, runner._prng)
    result = {"contract_version": CONTRACT, "upstream_sha": PAMS_SHA, "config": config,
              "input_hash": digest(config), "seed": seed, "backend_requested": backend,
              "backend_effective": backend, "events": logger.events, "steps": logger.steps,
              "initial": initial, "final": final, "rng": final["rng"]}
    result["hashes"] = {k: digest(result[k]) for k in ("events", "steps", "final", "rng")}
    return result
