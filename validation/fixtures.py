"""Generate actual upstream fixtures; no optimization formula used.

SPDX-License-Identifier: EPL-1.0
"""
import argparse
import copy
import json
from pathlib import Path
import random

from .codec import digest, encode
from .io import write
from .reference import collect


def small_config(pams_root):
    config = json.loads((Path(pams_root) / "samples/CI2002/config.json").read_text(encoding="utf-8"))
    config["FCNAgents"].update(numAgents=8, timeWindowSize=[2,4])
    for session in config["simulation"]["sessions"]:
        session.update(iterationSteps=3, maxNormalOrders=3, withPrint=False)
    return config


class RecordedRandom(random.Random):
    def __init__(self, state):
        super().__init__(0)
        self.setstate(state)
        self.calls = []

    def gauss(self, mu=0.0, sigma=1.0):
        value = super().gauss(mu, sigma)
        self.calls.append(value)
        return value


def numerical_fixture(config, seed, pams_root):
    from .upstream import load
    load(pams_root)
    from pams.runners import SequentialRunner
    from pams.agents import FCNAgent
    runner = SequentialRunner(settings=copy.deepcopy(config), prng=random.Random(seed))
    runner._setup()
    runner.simulator._update_times_on_markets(runner.simulator.markets)
    rows = []
    for agent in runner.simulator.agents:
        if type(agent) is not FCNAgent:
            continue
        agent.prng = RecordedRandom(agent.prng.getstate())
        for market in runner.simulator.markets:
            if not agent.is_market_accessible(market.market_id):
                continue
            effective_window = min(market.get_time(), agent.time_window_size)
            inputs = dict(p_now=market.get_market_price(), p_fund=market.get_fundamental_price(),
                          p_then=market.get_market_price(market.get_time()-effective_window),
                          w_f=agent.fundamental_weight, w_c=agent.chart_weight, w_n=agent.noise_weight,
                          noise_scale=agent.noise_scale, order_margin=agent.order_margin,
                          window=agent.time_window_size, effective_window=effective_window,
                          mean_reversion=agent.mean_reversion_time, margin_type=agent.margin_type,
                          chart_sign=1 if agent.is_chart_following else -1)
            before = encode(agent.prng.getstate())
            start = len(agent.prng.calls)
            orders = agent.submit_orders_by_market(market)
            calls = agent.prng.calls[start:]
            inputs.update(z_noise=calls[0], z_margin=calls[1] if len(calls)>1 else 0.0)
            rows.append(dict(agent_id=agent.agent_id, market_id=market.market_id, input=encode(inputs),
                             orders=encode(orders), gauss_api_calls=len(calls),
                             rng_before=before, rng_after=encode(agent.prng.getstate())))
    return {"seed": seed, "input_hash": digest(config), "rows": rows,
            "expected_source": "Actual FCNAgent.submit_orders_by_market; no copied formula"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pams-root", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    root = Path(a.output)
    root.mkdir(parents=True, exist_ok=False)
    config = small_config(a.pams_root)
    write(root/"config.json", config)
    trace = collect(config,42,a.pams_root)
    write(root/"upstream-trace.json.gz",trace)
    numeric = numerical_fixture(config,42,a.pams_root)
    write(root/"fcn-rows.json.gz",numeric)
    write(root/"schema-example.json",{"event":trace["events"][0], "step":trace["steps"][0]})
    from . import PAMS_SHA, CONTRACT
    from experiments.capture import environment, git
    import sys
    write(root/"provenance.json",{"upstream_sha":PAMS_SHA,"contract_version":CONTRACT,
                                  "git_sha":git("rev-parse","HEAD"),"dirty":bool(git("status","--porcelain")),
                                  "command":[sys.executable,"-m","validation.fixtures",*sys.argv[1:]],
                                  "environment":environment(),"config_hash":digest(config),
                                  "content_hashes":{"trace":digest(trace),"fcn":digest(numeric)},
                                  "scope":"MODULE fixture, not G0 system acceptance"})
    print(json.dumps({"events":len(trace["events"]),"steps":len(trace["steps"]),"fcn_rows":len(numeric["rows"])}))


if __name__ == "__main__":
    main()
