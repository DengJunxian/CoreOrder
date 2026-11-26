"""Independent oracle API; no coreorder/native/packing imports.

SPDX-License-Identifier: EPL-1.0
"""
import copy
import random
from contextlib import nullcontext

from . import CONTRACT, PAMS_SHA
from .codec import digest
from .stream import Checkpoints, inventory


def collect(config, seed, pams_root, backend="py-seq", workers=2, *, stream_path=None):
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
    metadata = {"contract_version": CONTRACT, "upstream_sha": PAMS_SHA, "config": config,
                "input_hash": digest(config), "seed": seed, "backend_requested": backend,
                "backend_effective": backend}
    with Checkpoints(stream_path, metadata) if stream_path else nullcontext() as output:
        logger.stream = output
        runner._setup()
        initial = logger.state()
        if output:
            output.emit("initial", initial)
        runner._run()
        logger._process()
        final = logger.state()
        if output:
            output.emit("final", final)
    if stream_path:
        return {**metadata, **inventory(stream_path)}
    result = {**metadata, "events": logger.events, "steps": logger.steps,
              "initial": initial["state"], "final": final["state"], "rng": final["state"]["rng"]}
    result["hashes"] = {k: digest(result[k]) for k in ("events", "steps", "final", "rng")}
    return result
