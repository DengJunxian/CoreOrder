"""Drive original PAMS runners and configure their optional worker pools."""

import random
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from time import perf_counter

from pams.runners import MultiProcessAgentParallelRunner, MultiThreadAgentParallelRunner, SequentialRunner
from pams.simulator import Simulator

from .market_adapter import CoreOrderMarket


class MeasuredSpawnPool(ProcessPoolExecutor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.copied_calls = 0
        self.copied_bytes = 0
        self.send_s = 0.0
        # CPython 3.12's feeder invokes this after serializing each actual task.
        send_bytes = self._call_queue._send_bytes

        def send(payload):
            started = perf_counter()
            send_bytes(payload)
            self.send_s += perf_counter() - started
            self.copied_calls += 1
            self.copied_bytes += len(payload)

        self._call_queue._send_bytes = send


class SpawnRunner(MultiProcessAgentParallelRunner):
    default_start_method = "spawn"
    _parallel_pool_provider = MeasuredSpawnPool

    def _create_executor(self):
        self.copy_metrics_pool = super()._create_executor()
        return self.copy_metrics_pool


def upstream_parallel_factory(backend, workers, **kwargs):
    cls = MultiThreadAgentParallelRunner if backend == "py-thread" else SpawnRunner
    runner = cls(**kwargs)
    settings = runner.settings["simulation"]
    if "numParallel" in settings and settings["numParallel"] != workers:
        raise ValueError("simulation.numParallel conflicts with --workers")
    if backend == "py-process" and settings.get("startMethod", "spawn") != "spawn":
        raise ValueError("py-process requires spawn")
    runner.num_parallel = workers
    return runner


def run_py_seq(
    config_path, seed, observer, *, book_restore="upstream", heap_diagnostics=None,
    simulator_class=Simulator, after_setup=None, runner_factory=SequentialRunner,
):
    started = perf_counter()
    runner = runner_factory(
        settings=config_path, prng=random.Random(seed), logger=observer, simulator_class=simulator_class,
    )
    observer.runner = runner
    try:
        if book_restore == "incremental":
            runner.class_register(CoreOrderMarket)
        runner._setup()
        if book_restore == "incremental":
            for market in runner.simulator.markets:
                if type(market) is not CoreOrderMarket:
                    raise ValueError("effective workload must select CoreOrderMarket for incremental restore")
                market.book_restore = book_restore
        if after_setup is not None:
            after_setup(runner)
        initialized = perf_counter()
        with heap_diagnostics.capture() if heap_diagnostics is not None else nullcontext():
            runner._run()
    finally:
        # Break the logger's backreference even when setup fails.
        observer.runner = None
        if isinstance(runner, MultiThreadAgentParallelRunner):
            runner._shutdown_executor()
    return runner, {"setup_s": initialized - started, "simulation_s": perf_counter() - initialized}
