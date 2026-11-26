"""Diagnostic spans at the same production call sites used by the P11 pilot."""

import heapq
import sys
from collections import Counter
from contextlib import contextmanager
from random import Random
from time import perf_counter_ns

from pams import Market
from pams.agents.fcn_agent import FCNAgent
from pams.runners import MultiThreadAgentParallelRunner, SequentialRunner
from pams.simulator import Simulator

from .heap_diagnostics import EXECUTION_CODE
from .native_serial import NativeSerialRunner

NATIVE_PHASES = ("draw_pack_s", "native_compute_s", "rebuild_orders_s")
PHASES = (*NATIVE_PHASES, "handle_orders_s", "optional_restore_s")
BATCH = NativeSerialRunner._evaluate_batch.__code__
TIMED = {
    SequentialRunner._handle_orders.__code__: "handle_orders_s",
    SequentialRunner._collect_orders_from_normal_agents.__code__: "python_collect",
    MultiThreadAgentParallelRunner._collect_orders_from_normal_agents.__code__: "python_collect",
    NativeSerialRunner._collect_orders_from_normal_agents.__code__: "native_collect",
    FCNAgent.submit_orders.__code__: "python_strategy",
    Random.sample.__code__: "sample",
    Random.gauss.__code__: "gauss",
    Market._collect_pending_executions.__code__: "matching_collect",
    Simulator._update_agents_for_execution.__code__: "account_updates",
}


class PhaseProfile:
    def __init__(self):
        self.totals = Counter()
        self.calls = Counter()
        self.active = {}

    @contextmanager
    def capture(self):
        previous = sys.getprofile()
        sys.setprofile(self.observe)
        try:
            yield
        finally:
            sys.setprofile(previous)

    def add(self, key, elapsed):
        self.totals[key] += elapsed
        self.calls[key] += 1

    def wrap_evaluator(self, evaluate):
        def observed(inputs):
            batch = sys._getframe(1)
            if batch not in self.active:
                return evaluate(inputs)
            start = perf_counter_ns()
            self.add("draw_pack_s", start - self.active[batch])
            result = evaluate(inputs)
            end = perf_counter_ns()
            self.add("native_compute_s", end - start)
            self.active[batch] = end
            return result

        return observed

    def observe(self, frame, event, arg):
        code = frame.f_code
        if code is BATCH:
            if event == "call":
                self.active[frame] = perf_counter_ns()
            elif event == "return":
                self.add("rebuild_orders_s", perf_counter_ns() - self.active.pop(frame))
            return

        name = TIMED.get(code)
        if name is not None:
            if event == "call":
                self.active[frame] = perf_counter_ns()
            elif event == "return":
                self.add(name, perf_counter_ns() - self.active.pop(frame))
        elif code in EXECUTION_CODE and arg in (heapq.heapify, heapq.heappush):
            if event == "c_call":
                self.active[frame] = perf_counter_ns()
            elif event == "c_return":
                self.add("optional_restore_s", perf_counter_ns() - self.active.pop(frame))

    def metrics(self, native):
        return {key: self.totals[key] / 1e9 for key in PHASES if native or key not in NATIVE_PHASES}
