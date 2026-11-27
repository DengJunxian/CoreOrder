"""Observe the pinned, unmodified PAMS event run; compare each live decision.

Requires D's src, pinned PAMS, and B's compiled _coreorder_fcn on PYTHONPATH.
Pass the G0 candidate fixtures/pams directory as argv[1].
"""

import hashlib
import json
import random
import struct
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import _coreorder_fcn
from pams.agents.fcn_agent import FCNAgent, MARGIN_NORMAL
from pams.events.fundamental_price_shock import FundamentalPriceShock
from pams.runners.sequential import SequentialRunner

from coreorder.packing import Draw, LayoutBuffer, pack_batch


def replay(fixtures):
    manifest = json.loads((fixtures / "manifest.json").read_bytes())
    key = "event-state/config.json"
    payload = (fixtures / key).read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != manifest["files"][key]:
        raise AssertionError("public configuration hash differs")
    print("input sha256", digest, "pams_sha", manifest["pams_sha"], "seed", manifest["seed"])
    runner = SequentialRunner(settings=json.loads(payload), prng=random.Random(manifest["seed"]))
    evaluator = _coreorder_fcn.Evaluator(parallel=False)
    buffers = [LayoutBuffer("aos"), LayoutBuffer("soa")]
    fcn_code = FCNAgent.submit_orders_by_market.__code__
    gauss_code = random.Random.gauss.__code__
    hook_code = FundamentalPriceShock.hooked_before_step_for_market.__code__
    observed = None
    phase = "before"
    counts = Counter()
    fundamentals = {}
    steps = {}
    output_digest = hashlib.sha256()

    def compare(agent, market, draws, orders):
        # The fixture has one market. Its per-market call index is exactly the
        # per-agent submission index consumed here.
        if len(runner.simulator.markets) != 1:
            raise AssertionError("this test requires the public single-market fixture")
        if len(draws) != (2 if agent.margin_type == MARGIN_NORMAL else 1) or len(orders) > 1:
            raise AssertionError("unexpected upstream draw/order counts")
        call = counts["calls"]
        identity = (agent.agent_id, market.market_id)
        values = Draw(*identity, *draws)
        order = orders[0] if orders else None
        if order and (order.agent_id, order.market_id) != identity:
            raise AssertionError("upstream order identity")
        bits = struct.pack("=dii", order.price if order else 0.0,
                           (1 if order.is_buy else -1) if order else 0, 0)
        state = agent.get_prng().getstate()
        live_fundamental = market.get_fundamental_price()
        step = market.get_time()
        for buf in buffers:
            with pack_batch(buf, [agent], [market], [values], first_call=call) as view:
                if view.metadata.tolist() != [(*identity, call)]:
                    raise AssertionError(f"{buf.layout}: metadata difference at {call}")
                if view.inputs["p_fund"][0].tobytes() != struct.pack("=d", live_fundamental):
                    raise AssertionError(f"{buf.layout}: stale fundamental at {step}")
                result = getattr(evaluator, buf.layout)(view.inputs)
                if result.tobytes() != bits:
                    raise AssertionError(f"call={call} id={identity} step={step} layout={buf.layout} "
                                         f"draws={[z.hex() for z in draws]} expected={bits.hex()} "
                                         f"actual={result.tobytes().hex()}")
            if agent.get_prng().getstate() != state:
                raise AssertionError(f"{buf.layout}: consumed extra agent RNG at {call}")
        fundamentals.setdefault(phase, set()).add(live_fundamental.hex())
        steps.setdefault(phase, []).append(step)
        counts.update({"calls": 1, phase: 1, "gauss": len(draws), "orders": len(orders)})
        output_digest.update(bits)

    def observe(frame, event, result):
        nonlocal phase, observed
        if frame.f_code is hook_code and event == "return":
            phase = "after"
            counts["shock_hooks"] += 1
        elif frame.f_code is fcn_code and event == "call":
            observed = (frame, frame.f_locals["self"], frame.f_locals["market"], [])
        elif observed is not None and event == "return":
            origin, agent, market, draws = observed
            if frame.f_code is gauss_code and frame.f_locals["self"] is agent.get_prng():
                draws.append(result)
            elif frame is origin:
                observed = None
                compare(agent, market, draws, result)

    previous = sys.getprofile()
    sys.setprofile(observe)
    try:
        runner.main()
    finally:
        sys.setprofile(previous)
    if counts["shock_hooks"] != 1 or not (counts["before"] and counts["after"]):
        raise AssertionError(f"shock boundary coverage: {counts}")
    if fundamentals["before"] & fundamentals["after"]:
        raise AssertionError(f"expected distinct pre/post shock fundamentals: {fundamentals}")
    print("counts", dict(counts))
    for part in ("before", "after"):
        print(part, "steps", steps[part], "fundamental prices", sorted(fundamentals[part]))
    print("all live outputs matched PAMS including price bytes and identity; observed agent RNG unchanged")
    print("ordered outputs sha256", output_digest.hexdigest())


if __name__ == "__main__":
    print("Python", sys.version, "NumPy", np.__version__, "binding", _coreorder_fcn.__file__)
    replay(Path(sys.argv[1]))
