"""A4 pilot diagnostics. All runs use pilot seeds and the pinned production code."""

import copy
import cProfile
import hashlib
from collections import Counter
from contextlib import nullcontext
from functools import partial
from pathlib import Path
import sys
from time import perf_counter_ns

from experiments.capture import execute, git
from validation.io import read, write

ROOT = Path.cwd()
SEEDS = (11, 29)
MODES = (("py-seq", "upstream"), ("py-seq", "incremental"), ("native-serial", "incremental"))


def workloads(path):
    original = ROOT / "vendor/pams/samples/CI2002/config.json"
    path.mkdir()
    full = path / "W0-CI2002.json"
    full.write_bytes(original.read_bytes())
    yield full
    for name, agents, quota, markets, warm, trade in (
        ("W4-START", 1024, 32, 1, 20, 100),
        ("W1-H", 4096, 32, 1, 20, 100),
        ("W2-H", 4096, 256, 1, 8, 24),
        ("W3-START", 16384, 1024, 4, 2, 8),
    ):
        settings = read(original)
        settings["FCNAgents"]["numAgents"] = agents
        for session in settings["simulation"]["sessions"]:
            session.update(maxNormalOrders=quota, withPrint=False)
        for session, steps in zip(settings["simulation"]["sessions"], (warm, trade), strict=True):
            session["iterationSteps"] = steps
        names = ["Market"] + [f"Market{i}" for i in range(1, markets)]
        for market in names[1:]:
            settings[market] = copy.deepcopy(settings["Market"])
        settings["simulation"]["markets"] = settings["FCNAgents"]["markets"] = names
        output = path / f"{name}.json"
        write(output, settings)
        yield output


def digest_final(runner):
    from coreorder.config import json_bytes
    from coreorder.snapshot import final_state, market_history, random_state

    sim = runner.simulator
    rng = hashlib.sha256()
    for group in (
        [runner._prng, sim._prng, sim.fundamentals._prng],
        [m._prng for m in sim.markets], [a.prng for a in sim.agents],
        [s.prng for s in sim.sessions], [e.prng for e in sim.events],
    ):
        rng.update(json_bytes(len(group)))
        for random in group:
            rng.update(json_bytes(random_state(random)))
    rng.update(json_bytes(sim.fundamentals._np_prng.bit_generator.state))
    state = {**final_state(sim), "market_history": market_history(sim)}
    return hashlib.sha256(json_bytes(state)).hexdigest(), rng.hexdigest()


class Phases:
    def __init__(self, captured=None):
        from pams import Market
        from pams.agents.fcn_agent import FCNAgent
        from pams.runners import SequentialRunner
        from pams.simulator import Simulator
        from random import Random

        from coreorder.native_serial import NativeSerialRunner
        from coreorder.packing import pack_batch

        self.pending = Market._collect_pending_executions.__code__
        self.execute = Market._execute_orders.__code__
        self.batch = NativeSerialRunner._evaluate_batch.__code__
        self.pack = pack_batch.__code__
        self.timed = {
            SequentialRunner._collect_orders_from_normal_agents.__code__: "collect",
            NativeSerialRunner._collect_orders_from_normal_agents.__code__: "collect",
            SequentialRunner._handle_orders.__code__: "handle",
            SequentialRunner._process_order.__code__: "process_order",
            Market._add_order.__code__: "book_insert",
            Market._execution.__code__: "execution_total",
            self.pending: "matching_collect",
            self.execute: "execute_orders",
            Simulator._update_agents_for_execution.__code__: "account_updates",
            FCNAgent.submit_orders.__code__: "python_strategy",
            Random.gauss.__code__: "gauss",
        }
        from coreorder.market_adapter import CoreOrderMarket
        self.timed[CoreOrderMarket._execution.__code__] = "execution_total"
        self.sums = Counter()
        self.counts = Counter()
        self.starts = {}
        self.restore = {}
        self.native = {}
        self.captured = captured
        self.captured_count = 0

    def add(self, name, duration):
        self.sums[name] += duration
        self.counts[name] += 1

    def observe(self, frame, event, value):
        code = frame.f_code
        if code == self.batch:
            if event == "call":
                self.native[frame] = [perf_counter_ns()]
            elif event in ("c_call", "c_return") and getattr(value, "__name__", None) == "aos":
                now = perf_counter_ns()
                state = self.native[frame]
                if event == "c_call":
                    if self.captured is not None and self.captured_count < 8192:
                        batch = frame.f_locals["batch"]
                        rows = batch.inputs[:8192 - self.captured_count]
                        self.captured.write(rows.tobytes())
                        self.captured_count += len(rows)
                    state.append(now)
                    self.add("packing_and_lease", now - state[1])
                else:
                    self.add("native_binding", now - state[2])
                    state.append(now)
            elif event == "return":
                spans = self.native.pop(frame)
                if len(spans) == 4:
                    self.add("rebuild_and_release", perf_counter_ns() - spans[3])
        elif code == self.pack and event == "call":
            owner = frame.f_back
            if owner in self.native:
                spans = self.native[owner]
                now = perf_counter_ns()
                self.add("draw_preparation", now - spans[0])
                spans.append(now)
        name = self.timed.get(code)
        if name is None:
            return
        if event == "call":
            now = perf_counter_ns()
            self.starts[frame] = now
            if code == self.execute and frame.f_back in self.restore:
                self.add("restore_span", now - self.restore.pop(frame.f_back))
        elif event == "return":
            now = perf_counter_ns()
            self.add(name, now - self.starts.pop(frame))
            if code == self.pending and value is not None and value[1] is not None:
                self.restore[frame.f_back] = now


def child(config, seed, backend, restore, purpose, output):
    from pams.logs import Logger

    from coreorder.config import incremental_workload, json_bytes, sha256
    from coreorder.heap_diagnostics import HeapDiagnostics
    from coreorder.market_adapter import CoreOrderMarket
    from coreorder.native_serial import NativeSerialRunner, load_native_serial
    from coreorder.runner import run_py_seq
    from coreorder.snapshot import PamsObservations

    class EventsOnly(PamsObservations):
        def process_market_step_end_log(self, log):
            self.market_steps += 1

    assert seed in SEEDS
    output.mkdir()
    settings = read(config)
    raw = config.read_bytes()
    (output / "workload.json").write_bytes(raw)
    effective = output / "effective_config.json"
    effective.write_bytes(json_bytes(incremental_workload(settings)) if restore == "incremental" else raw)
    counters = HeapDiagnostics(sizes=True, comparisons=True) if purpose == "heap" else None
    profiling = cProfile.Profile() if purpose == "profile" else None
    native_identity = None
    options = {}
    if backend == "native-serial":
        module = load_native_serial()
        library = Path(module.__file__).resolve()
        evaluator = module.Evaluator(parallel=False)
        native_identity = {"path": str(library), "sha256": sha256(library.read_bytes())}
        options["runner_factory"] = partial(
            NativeSerialRunner, evaluate=evaluator.aos,
            market_adapter=CoreOrderMarket if restore == "incremental" else None,
        )
    manifest = {"backend_requested": backend, "backend_effective": backend, "book_restore": restore,
                "native": native_identity, "seed": seed, "workload_id": config.stem,
                "git_sha": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain")),
                "contract_version": "coreorder-r4-v1", "measurement_mode": purpose,
                "input_hash": sha256(raw), "effective_hash": sha256(effective.read_bytes())}
    write(output / "manifest.json", manifest)
    capture_path = output / "input.aos"
    capture = capture_path.open("wb") if purpose == "capture" else nullcontext(None)
    events = (output / "events.jsonl").open("wb") if purpose == "verify" else nullcontext(None)
    with capture as captured, events as stream:
        phase = Phases(captured) if purpose in ("phases", "capture") else None
        logger = EventsOnly(stream, None, None, "p11") if stream else Logger()
        if phase:
            def after_setup(_):
                sys.setprofile(phase.observe)
        elif profiling:
            def after_setup(_):
                profiling.enable()
        else:
            after_setup = None
        try:
            runner, durations = run_py_seq(
                effective, seed, logger, book_restore=restore, heap_diagnostics=counters,
                after_setup=after_setup, **options,
            )
        finally:
            if phase:
                sys.setprofile(None)
            if profiling:
                profiling.disable()
    if profiling:
        profiling.dump_stats(str(output / "profile.prof"))
    state, rng = digest_final(runner)
    summary = {
        **durations, "state_hash": state, "rng_hash": rng, "market_count": len(runner.simulator.markets),
        "quotas": [s.max_normal_orders for s in runner.simulator.sessions],
        "orders_admitted": sum(m._next_order_id for m in runner.simulator.markets),
        "agent_count": len(runner.simulator.agents),
        "scope": ("PAMS simulation with plain Logger, no phase hooks or trace; final digest outside timer"
                  if purpose == "timing" else "instrumented pilot; timing is diagnostic only"),
    }
    if stream:
        summary.update(event_hash=logger.event_digest.hexdigest(),
                       event_counts=dict(logger.counts), market_steps=logger.market_steps)
    if counters:
        write(output / "heap.json", counters.report())
    if phase:
        if backend == "native-serial":
            assert phase.counts["native_binding"] == len(runner.batch_widths) > 0
        write(output / "phases.json", {"nanoseconds": dict(phase.sums), "calls": dict(phase.counts)})
        if captured:
            assert phase.captured_count > 0
            write(output / "capture.json", {"rows": phase.captured_count, "stride": 112,
                                             "sha256": sha256(capture_path.read_bytes())})
    if backend == "native-serial":
        summary.update(native_rows=runner.native_rows, gauss_api_calls=runner.gauss_api_calls,
                       agent_calls=runner.agent_calls, native_executor_creations=module.executor_creations())
    write(output / "summary.json", summary)
    print(config.stem, backend, restore, purpose, seed, durations, flush=True)


def pilot(root):
    root.mkdir()
    files = {path.stem: path.resolve() for path in workloads(root / "workloads")}
    plan = {name: read(path)["simulation"] for name, path in files.items()}
    write(root / "plan.json", {"configurations": plan, "seeds": SEEDS, "timeout_s": 30,
                                "purpose": "local preparatory diagnosis; not G3 or formal timing"})
    records = []

    def run(name, seed, backend, restore, purpose, timeout=30):
        title = f"{name}-{seed}-{backend}-{restore}-{purpose}"
        output = root / title
        cmd = [sys.executable, "-B", __file__, "child", str(files[name]), str(seed), backend,
               restore, purpose, str(output)]
        receipt = execute(cmd, root / f"{title}-command", timeout)
        result = {"case": title, "workload": name, "seed": seed, "backend": backend, "restore": restore,
                  "purpose": purpose, "status": receipt["status"], "timeout_s": timeout,
                  "process_elapsed_s": receipt["elapsed_s_driver"], "run": str(output)}
        if receipt["status"] == "PASS":
            result["summary"] = read(output / "summary.json")
        records.append(result)
        print(title, receipt["status"], round(receipt["elapsed_s_driver"], 3), flush=True)
        return result

    def match(results):
        passed = [r for r in results if r["status"] == "PASS"]
        if not passed:
            return
        keys = ("state_hash", "rng_hash", "orders_admitted")
        reference = passed[0]["summary"]
        for candidate in passed[1:]:
            fields = keys + (("event_hash", "event_counts", "market_steps")
                             if "event_hash" in reference and "event_hash" in candidate["summary"] else ())
            for field in fields:
                if reference[field] != candidate["summary"][field]:
                    write(root / "first-difference.json", {
                        "field": field, "reference": passed[0], "candidate": candidate,
                    })
                    raise AssertionError((candidate["case"], field))

    planned = ("W4-START", "W0-CI2002", "W1-H", "W2-H", "W3-START")
    for name in planned:
        for seed in SEEDS:
            modes = MODES if name in ("W4-START", "W2-H", "W3-START") else MODES[:2]
            verify = [run(name, seed, *mode, "verify") for mode in modes]
            match(verify)
            ordered = modes if seed == SEEDS[0] else tuple(reversed(modes))
            timing = [run(name, seed, *mode, "timing") for mode in ordered]
            match(verify + timing)
            write(root / f"checkpoint-{name}-{seed}.json", records)
    for name in ("W0-CI2002", "W1-H", "W2-H"):
        for seed in SEEDS:
            counters = [run(name, seed, *mode, "heap") for mode in MODES[:2]]
            match(counters)
    for mode in MODES:
        for purpose in ("profile", "phases"):
            probe = run("W1-H", 11, *mode, purpose)
            match([row for row in records if row["workload"] == "W1-H" and row["seed"] == 11
                   and row["purpose"] == "verify"] + [probe])
    run("W2-H", 11, *MODES[2], "capture")
    write(root / "chronological.json", records)
    print("outcomes", dict(Counter(r["status"] for r in records)), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "child":
        config, seed, backend, restore, purpose, output = sys.argv[2:]
        child(Path(config), int(seed), backend, restore, purpose, Path(output))
    else:
        pilot(Path(sys.argv[1]).resolve())
