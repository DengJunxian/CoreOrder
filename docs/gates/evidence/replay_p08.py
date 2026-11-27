"""Read-only P08 audit of the production AoS runner and its error boundary."""

import hashlib
import importlib.util
import json
import random
import subprocess
import sys
import threading
import warnings
from collections import defaultdict
from functools import partial
from pathlib import Path

import numpy as np
from pams.agents.base import Agent
from pams.agents.fcn_agent import FCNAgent
from pams.runners.sequential import SequentialRunner

from coreorder.config import ROOT
from coreorder.native_serial import NativeSerialRunner, load_native_serial
from coreorder.packing import INPUT_DTYPE, OUTPUT_DTYPE, _Writer
from coreorder.runner import run_py_seq
from validation.collector import TraceLogger
from validation.compare import first_diff
from validation.io import read, write

SEED = 42
NAMES = ("smoke", "native-serial-normal")


def numerical(member_b, output, native):
    """Extend B's independent test-only generator to 112 agents."""
    source = member_b / "tests/native/fcn_cases.py"
    sys.path.insert(0, str(source.parent))
    spec = importlib.util.spec_from_file_location("fcn_cases", source)
    cases = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cases
    body = source.read_text()
    assert body.count("for agent_id in range(100):") == 1
    exec(compile(body.replace("for agent_id in range(100):", "for agent_id in range(112):"),
                 str(source), "exec"), vars(cases))
    cases.ROOT = ROOT
    from test_fcn import assert_orders

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="price should be positive")
        rows, expected, identity, counts, orders = cases.generated_cases()
        actual = native.Evaluator(parallel=False).aos(rows)
        assert_orders(actual, rows, expected, identity, orders)
    assert len(rows) >= 10_000 and len(rows) + counts["inaccessible"] == 11_200
    assert all(counts[key] > 0 for key in ("margin_0_chart_-1", "margin_0_chart_1",
                                           "margin_1_chart_-1", "margin_1_chart_1", "prefilled_agents",
                                           "inaccessible", "window_zero", "time_zero", "normal_empty"))
    assert rows.dtype == INPUT_DTYPE and actual.dtype == OUTPUT_DTYPE
    assert rows.dtype.isnative and actual.dtype.isnative
    assert rows.dtype.alignment == actual.dtype.alignment == 8
    assert rows.strides == (112,) and actual.strides == (16,)
    assert rows.ctypes.data % 8 == actual.ctypes.data % 8 == 0
    result = {"status": "PASS", "valid": len(rows), "attempted": 11_200, **counts,
              "generator_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "inputs_sha256": hashlib.sha256(rows.tobytes()).hexdigest(),
              "outputs_sha256": hashlib.sha256(actual.tobytes()).hexdigest(),
              "byteorder": sys.byteorder, "input_stride": rows.strides, "output_stride": actual.strides}
    write(output / "numerical.json", result)
    print("NUMERICAL", result, flush=True)


def rng_state(prng):
    version, state, gauss_cache = prng.getstate()
    return [version, list(state), gauss_cache.hex() if gauss_cache is not None else None]


def order_record(order):
    return [order.agent_id, order.market_id, order.kind.kind_id, order.is_buy,
            order.volume, order.ttl, float(order.price).hex()]


def observe(config, backend, native):
    events = defaultdict(list)
    collect = (SequentialRunner._collect_orders_from_normal_agents.__code__,
               NativeSerialRunner._collect_orders_from_normal_agents.__code__)
    upstream_market = FCNAgent.submit_orders_by_market.__code__
    native_batch = NativeSerialRunner._evaluate_batch.__code__
    thread = threading.get_ident()

    def observe_frame(frame, event, value):
        if event not in ("call", "return"):
            return
        code = frame.f_code
        parent = frame.f_back
        if code == random.Random.sample.__code__ and parent.f_code in collect:
            state = rng_state(frame.f_locals["self"])
            if event == "call":
                events["sample_before"].append(state)
            else:
                events["sample_after"].append([[agent.agent_id for agent in value], state])
        elif event == "call" and code == FCNAgent.submit_orders.__code__:
            events["activation"].append(frame.f_locals["self"].agent_id)
        elif event == "call" and code == native_batch:
            agents = frame.f_locals["agents"]
            events["activation"].extend(agent.agent_id for agent in agents)
            events["widths"].append(len(agents))
        elif code == Agent.is_market_accessible.__code__ and parent.f_code in (upstream_market, native_batch):
            if event == "return":
                events["market_visits"].append([frame.f_locals["self"].agent_id,
                                                 frame.f_locals["market_id"], value])
        elif code == random.Random.gauss.__code__ and parent.f_code in (upstream_market, native_batch):
            assert threading.get_ident() == thread
            agent = parent.f_locals["self" if parent.f_code == upstream_market else "agent"]
            market = parent.f_locals["market"]
            state = rng_state(frame.f_locals["self"])
            if event == "call":
                events["gauss_before"].append([agent.agent_id, market.market_id, state])
            else:
                events["gauss_after"].append([value.hex(), state])
        elif event == "call" and code == SequentialRunner._check_submitted_orders.__code__:
            events["upstream_order_check"].append([order_record(o) for o in frame.f_locals["orders"]])
        elif event == "call" and code == SequentialRunner._handle_orders.__code__:
            events["upstream_handle"].append([[order_record(o) for o in group]
                                               for group in frame.f_locals["local_orders"]])
        elif event == "return" and code in collect:
            events["quota"].append([frame.f_locals["session"].max_normal_orders, len(value)])

    evaluator = native.Evaluator(parallel=False)
    runner = None
    final_output = None

    def after_setup(instance):
        nonlocal runner
        runner = instance

    def evaluate(rows):
        nonlocal final_output
        assert not rows.flags.writeable and rows.base is not None
        try:
            with runner._layout_buffer.fill(0):
                raise AssertionError("D allowed refill during an active lease")
        except RuntimeError as error:
            assert str(error) == "layout buffer in use"
        previous = final_output
        result = evaluator.aos(rows)
        assert result.flags.owndata and not np.shares_memory(result, rows)
        if previous is not None:
            assert previous[0].tobytes() == previous[1]
        final_output = (result, result.tobytes())
        events["leased_calls"].append(len(rows))
        return result

    options = {}
    if backend == "native-serial":
        options["runner_factory"] = partial(NativeSerialRunner, evaluate=evaluate)
    sys.setprofile(observe_frame)
    try:
        run_py_seq(config, SEED, TraceLogger(), after_setup=after_setup, **options)
    finally:
        sys.setprofile(None)
    return dict(events)


def runner_boundary(output, native):
    for name in NAMES:
        config = ROOT / "configs/workloads" / f"{name}.json"
        reference = observe(config, "py-seq", native)
        candidate = observe(config, "native-serial", native)
        widths = candidate.pop("widths")
        leases = candidate.pop("leased_calls")
        result = first_diff(reference, candidate)
        if result is not None:
            write(output / f"{name}-call-first-difference.json",
                  {"reference": reference, "candidate": candidate, "first": result, "seed": SEED})
            raise AssertionError(result)
        assert sum(widths) == len(reference["activation"]) and len(widths) == len(leases)
        assert all(used <= limit for limit, used in reference["quota"])
        write(output / f"{name}-calls.json.gz", reference)
        summary = {"status": "PASS", "seed": SEED, "sample": len(reference["sample_after"]),
                   "activation": len(reference["activation"]), "market_visits": len(reference["market_visits"]),
                   "inaccessible": sum(not row[2] for row in reference["market_visits"]),
                   "gauss": len(reference["gauss_after"]),
                   "prefilled_gauss_calls": sum(row[2][2] is not None for row in reference["gauss_before"]),
                   "checks": len(reference["upstream_order_check"]), "handle": len(reference["upstream_handle"]),
                   "widths": widths, "leases": leases}
        write(output / f"{name}-calls-summary.json", summary)
        print("CALLS", name, summary, flush=True)


def reproduce(output, native):
    settings = read(ROOT / "configs/workloads/smoke.json")
    common = settings.pop("FCNAgents")
    common.update(numAgents=1, fundamentalWeight=0, chartWeight=0, noiseWeight=0,
                  timeWindowSize=2, orderMargin=0, meanReversionTime=2, noiseScale=0.001)
    settings["ZeroWeight"] = common
    settings["NonFinite"] = dict(common, fundamentalWeight=1, noiseScale={"uniform": [-1e308, 1e308]})
    settings["simulation"]["agents"] = ["ZeroWeight", "NonFinite"]
    sessions = settings["simulation"]["sessions"]
    sessions[:] = [dict(sessions[0], iterationSteps=1, maxNormalOrders=2)]
    assert "hifreqSubmitRate" in sessions[0]
    del sessions[0]["hifreqSubmitRate"]
    workload = output / "workload.json"
    write(workload, settings)

    seed = 3
    captured = []
    rng = {}
    batch_code = NativeSerialRunner._evaluate_batch.__code__

    def capture(frame, event, value):
        if frame.f_code == _Writer.set_row.__code__ and event == "call":
            local = frame.f_locals
            captured.append((local["i"], local["values"], local["metadata"]))
        elif frame.f_code == batch_code and event in ("call", "return"):
            rng[event] = [rng_state(agent.prng) for agent in frame.f_locals["agents"]]

    evaluator = native.Evaluator(parallel=False)
    factory = partial(NativeSerialRunner, evaluate=evaluator.aos)
    sys.setprofile(capture)
    try:
        try:
            run_py_seq(workload, seed, TraceLogger(), runner_factory=factory)
        except ValueError as error:
            assert "row 1" in str(error) and "non-finite numeric field" in str(error)
        else:
            raise AssertionError("The invalid batch was accepted")
    finally:
        sys.setprofile(None)

    assert [index for index, _, _ in captured] == [0, 1]
    rows = np.array([values for _, values, _ in captured], dtype=INPUT_DTYPE)
    assert all(rows[0][name] == 0 for name in ("w_f", "w_c", "w_n"))
    assert rows[1]["noise_scale"] == float("inf")
    write(output / "canonical-rows.json", [
        {"row": i, "metadata": identity, "input": {
            name: float(value).hex() if INPUT_DTYPE[name].kind == "f" else int(value)
            for name, value in zip(INPUT_DTYPE.names, values, strict=True)}}
        for i, values, identity in captured
    ])
    assert len(rng["call"]) == len(rng["return"]) == 2 and rng["call"] != rng["return"]
    write(output / "rng-before-after-batch.json.gz", rng)
    try:
        evaluator.aos(rows)
    except ValueError as error:
        direct_error = str(error)
        assert direct_error == "FCN row 0 failed with error 1"
    else:
        raise AssertionError("The binding accepted both invalid rows")

    findings = {}
    for label, requested in (("actual", "native-serial"), ("reference", "py-seq"),
                              ("row0-control", "native-serial")):
        source = workload
        if label == "row0-control":
            settings["simulation"]["agents"].remove("NonFinite")
            del settings["NonFinite"]
            source = output / "row0-control.json"
            write(source, settings)
        target = output / label
        command = [sys.executable, "-B", "-m", "coreorder", "run", "--config", str(source),
                   "--seed", str(seed), "--backend", requested, "--book-restore", "upstream",
                   "--output", str(target)]
        run = subprocess.run(command, capture_output=True, text=True, timeout=60)
        write(output / f"{label}-command.json", {"argv": command, "cwd": str(ROOT), "exit": run.returncode})
        (output / f"{label}.stdout").write_text(run.stdout)
        (output / f"{label}.stderr").write_text(run.stderr)
        record = read(target / "status.json")
        manifest = read(target / "manifest.json")
        assert run.returncode == 1 and record["status"] == "FAIL" and manifest["backend_effective"] == requested
        assert (target / "events.jsonl").read_bytes() == b"" and not (target / "final_rng.json").exists()
        findings[label] = record["reason"]
    assert "row 1" in findings["actual"] and "non-finite numeric field" in findings["actual"]
    assert "FCN row 0 failed with error 1" in findings["row0-control"]
    assert "division by zero" in findings["reference"]
    result = {"status": "BLOCKED", "seed": seed, "first_row": "ZeroWeight",
              "second_row": "NonFinite", "derived_noise_scale": float(rows[1]["noise_scale"]).hex(),
              "first_difference": {"expected_index": 0, "reported_index": 1},
              "direct_same_rows": direct_error, **findings}
    write(output / "first-divergence.json", result)
    print("FAILURE ORDER", result, flush=True)


if __name__ == "__main__":
    mode, path = sys.argv[1:3]
    output = Path(path).resolve()
    output.mkdir()
    native = load_native_serial()
    if mode == "numerical":
        numerical(Path(sys.argv[3]).resolve(), output, native)
    elif mode == "calls":
        runner_boundary(output, native)
    elif mode == "failure":
        reproduce(output, native)
    else:
        raise ValueError(mode)
