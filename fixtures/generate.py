"""Generate reproducible A-side fixtures by observing the fixed PAMS implementation."""

import argparse
import gzip
import io
import json
import random
import sys
from pathlib import Path

from pams.agents.fcn_agent import FCNAgent, MARGIN_NORMAL
from pams.runners.sequential import SequentialRunner

from coreorder.config import ROOT, json_bytes, sha256
from coreorder.environment import environment
from coreorder.reference import run_upstream
from coreorder.snapshot import (
    PamsObservations, final_rng, final_state, fcn_state, market_history, price_hex, random_state,
)

SEED = 42


def write_json(path, value):
    path.write_bytes(json_bytes(value))


def compress(path, payload):
    path.write_bytes(gzip.compress(payload, mtime=0))


def capture_market(directory, config, label):
    directory.mkdir()
    path = directory / "config.json"
    path.write_bytes(config)
    with (directory / "events.jsonl").open("wb") as events, (directory / "market_steps.jsonl").open("wb") as steps:
        step_states = io.BytesIO()
        observer = PamsObservations(events, steps, step_states, label)
        runner, _ = run_upstream(path, SEED, observer)
    write_json(directory / "final_state.json", {
        "initial_accounts": observer.initial_accounts,
        **final_state(runner.simulator),
        "market_history": market_history(runner.simulator),
    })
    compress(directory / "step_states.jsonl.gz", step_states.getvalue())
    compress(directory / "final_rng.json.gz", json_bytes(final_rng(runner)))
    return {**dict(observer.counts), "market_steps": observer.market_steps}


def capture_fcn(config, mode):
    rows, states = [], []
    active = None
    fcn_code = FCNAgent.submit_orders_by_market.__code__
    gauss_code = random.Random.gauss.__code__
    runner = SequentialRunner(settings=config, prng=random.Random(SEED))

    def profile(frame, event, value):
        nonlocal active
        if frame.f_code is fcn_code and event == "call" and len(rows) < 12:
            agent, market = frame.f_locals["self"], frame.f_locals["market"]
            if not agent.is_market_accessible(market.market_id):
                return
            step = market.get_time()
            window = min(step, agent.time_window_size)
            active = {
                "frame": frame,
                "agent": agent,
                "draws": [],
                "before": random_state(agent.prng),
                "row": {
                    "workload": mode,
                    "call_index": len(rows),
                    "agent_id": agent.agent_id,
                    "market_id": market.market_id,
                    "step": step,
                    "input": {
                        **fcn_state(agent),
                        "effective_window": window,
                        "p_now": price_hex(market.get_market_price()),
                        "p_fund": price_hex(market.get_fundamental_price()),
                        "p_then": price_hex(market.get_market_price(step - window)),
                    },
                },
            }
        elif active is not None and event == "return":
            agent = active["agent"]
            if frame.f_code is gauss_code and frame.f_locals["self"] is agent.prng:
                active["draws"].append(value)
            elif frame is active["frame"]:
                row = active["row"]
                draws = active["draws"]
                normal = agent.margin_type == MARGIN_NORMAL
                if len(draws) != (2 if normal else 1) or not isinstance(value, list) or len(value) > 1:
                    raise ValueError("unexpected fixed PAMS FCN return or draw count")
                row["input"].update(z_noise=price_hex(draws[0]), z_margin=price_hex(draws[1] if normal else 0.0))
                order = value[0] if value else None
                row["output"] = {
                    "price": price_hex(order.price if order else 0.0),
                    "side": (1 if order.is_buy else -1) if order else 0,
                    "error": 0,
                }
                row["volume"] = order.volume if order else 0
                row["ttl"] = order.ttl if order else None
                before, after = active["before"], random_state(agent.prng)
                row["rng_before_hash"] = sha256(json_bytes(before))
                row["rng_after_hash"] = sha256(json_bytes(after))
                rows.append(row)
                states.append({"workload": mode, "call_index": row["call_index"], "before": before, "after": after})
                active = None

    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        runner.main()
    finally:
        sys.setprofile(previous)
    if len(rows) != 12:
        raise ValueError("the fixed run did not yield the required FCN observations")
    return rows, states


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    env = environment()
    upstream = env["upstream"]["PAMS"]
    if (
        upstream["dirty"] or upstream["sha"] != upstream["required_sha"]
        or env["pams_install_source"] != (ROOT / "vendor/pams").as_uri()
        or not env["pams_distribution_matches_import"]
        or env["pams_version"] != upstream["required_version"]
    ):
        raise ValueError("fixtures require the unchanged fixed PAMS installation")
    out.mkdir(parents=True, exist_ok=False)
    smoke = (ROOT / "configs/workloads/smoke.json").read_bytes()
    smoke_counts = capture_market(out / "ci2002-smoke", smoke, "fixture-ci2002-smoke")

    event = json.loads(smoke)
    event["FCNAgents"].update(numAgents=12, timeWindowSize=[2, 5])
    warmup, trading = event["simulation"]["sessions"]
    warmup["iterationSteps"] = 8
    trading.update(iterationSteps=16, events=["Shock"])
    event["Shock"] = {
        "class": "FundamentalPriceShock", "target": "Market", "triggerTime": 2, "priceChangeRate": -0.1,
    }
    event_counts = capture_market(out / "event-state", json_bytes(event), "fixture-event-state")

    directory = out / "fcn"
    directory.mkdir()
    rows, states = [], []
    for mode in ("fixed", "normal"):
        config = json.loads(smoke)
        config["FCNAgents"]["marginType"] = mode
        write_json(directory / f"{mode}.json", config)
        observed_rows, observed_states = capture_fcn(config, mode)
        rows.extend(observed_rows)
        states.extend(observed_states)
    (directory / "rows.jsonl").write_bytes(b"".join(json_bytes(row) for row in rows))
    compress(directory / "rng.json.gz", json_bytes(states))

    manifest = {
        "contract_version": env["contract_version"],
        "pams_sha": upstream["sha"],
        "pams_version": env["pams_version"],
        "seed": SEED,
        "command": f".venv/bin/python fixtures/generate.py --output {out}",
        "generator_sha256": sha256(Path(__file__).read_bytes()),
        "environment": {
            "os": env["os"], "architecture": env["architecture"], "python": env["python"],
            "packages": {name: env["packages"][name] for name in ("numpy", "scipy", "tqdm")},
        },
        "observations": {"ci2002-smoke": smoke_counts, "event-state": event_counts, "fcn_rows": len(rows)},
        "files": {
            path.relative_to(out).as_posix(): sha256(path.read_bytes())
            for path in sorted(out.rglob("*")) if path.is_file()
        },
    }
    write_json(out / "manifest.json", manifest)
    print(json.dumps(manifest["observations"], sort_keys=True))


if __name__ == "__main__":
    main()
