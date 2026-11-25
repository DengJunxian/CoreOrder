"""P02 production path using PAMS setup and execution in their original order."""

import random
from time import perf_counter

from pams.runners.sequential import SequentialRunner


def run_py_seq(config_path, seed, observer):
    started = perf_counter()
    runner = SequentialRunner(settings=config_path, prng=random.Random(seed), logger=observer)
    runner._setup()
    initialized = perf_counter()
    runner._run()
    return runner, {"setup_s": initialized - started, "simulation_s": perf_counter() - initialized}
