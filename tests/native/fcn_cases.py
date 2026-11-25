"""Real PAMS calls and public replay data for B's isolated test harness."""

import gzip
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from coreorder.contracts import INPUT_DTYPE

sys.path.insert(0, str(Path(__file__).resolve().parent / "b1"))
from oracle import load_pams, order_key

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures" / "pams"


def columns(rows):
    # NumPy can report a singleton structured column as contiguous at stride 112.
    return {name: rows[name].copy(order="C") for name in INPUT_DTYPE.names}


def public_replay():
    manifest = json.loads((FIXTURES / "manifest.json").read_bytes())
    payload = (FIXTURES / "fcn/rows.jsonl").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == manifest["files"]["fcn/rows.jsonl"]
    entries = [json.loads(line) for line in payload.splitlines()]
    inputs = np.array([
        tuple(float.fromhex(entry["input"][name]) if INPUT_DTYPE[name].kind == "f"
              else entry["input"][name] for name in INPUT_DTYPE.names)
        for entry in entries
    ], dtype=INPUT_DTYPE)
    return inputs, entries


def random_state(record):
    cache = record["gauss_next_hex"]
    return record["version"], tuple(record["state"]), None if cache is None else float.fromhex(cache)


def public_rng():
    manifest = json.loads((FIXTURES / "manifest.json").read_bytes())
    payload = (FIXTURES / "fcn/rng.json.gz").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == manifest["files"]["fcn/rng.json.gz"]
    return json.loads(gzip.decompress(payload))


class ObservedRandom(random.Random):
    def __init__(self, seed):
        super().__init__(seed)
        self.draws = []

    def gauss(self, mu=0.0, sigma=1.0):
        value = super().gauss(mu, sigma)
        self.draws.append(value.hex())
        return value


def generated_cases():
    fcn, market_module, order_module = load_pams(ROOT / "vendor/pams")
    maker = random.Random(20261125)
    inputs, expected_orders, metadata = [], [], []
    counts = Counter()
    for agent_id in range(100):
        seed = 700001 + agent_id
        upstream_rng = ObservedRandom(seed)
        replay_rng = random.Random(seed)
        if agent_id % 2:
            upstream_rng.gauss(0.0, 1.0)
            replay_rng.gauss(0.0, 1.0)
            counts["prefilled_agents"] += 1
        agent = fcn.FCNAgent(agent_id, upstream_rng, None, "b-fcn")
        for call in range(100):
            index = agent_id + call
            market_id = 1 + call % 3
            accessible = index % 11 != 0
            time = [0, 1, 7, 30, 80][index % 5]
            window = [0, 1, 5, 20, 80][(agent_id * 3 + call) % 5]
            effective = min(time, window)
            now = maker.uniform(100, 5000)
            fundamental = now * maker.uniform(0.98, 1.02)
            past = now * maker.uniform(0.98, 1.02)
            noise_scale = maker.uniform(0, 0.005)
            if index % 13 == 0:
                fundamental = past = now
                noise_scale = 0.0
            if effective == 0:
                past = now
            mean_reversion = 0 if index % 17 == 0 else max(window, 1)
            weights = [maker.uniform(0.1, 5.0) for _ in range(3)]
            chart_sign = 1 if ((agent_id + 3 * call) // 2) % 2 else -1
            margin_type = fcn.MARGIN_FIXED if index % 2 else fcn.MARGIN_NORMAL
            margin = maker.uniform(0, 0.2)
            if index % 37 == 0 and margin_type == fcn.MARGIN_FIXED:
                margin = 1.0

            agent.asset_volumes = {market_id: 100} if accessible else {}
            agent.fundamental_weight, agent.chart_weight, agent.noise_weight = weights
            agent.noise_scale = noise_scale
            agent.time_window_size = window
            agent.mean_reversion_time = mean_reversion
            agent.is_chart_following = chart_sign == 1
            agent.margin_type = margin_type
            agent.order_margin = margin
            market = market_module.Market(market_id, random.Random(42), None, "fixture-market")
            market.time = time
            market._market_prices = [past] * time + [now]
            market._fundamental_prices = [fundamental] * (time + 1)

            upstream_rng.draws.clear()
            orders = agent.submit_orders_by_market(market)
            draws = []
            if accessible:
                draws.append(replay_rng.gauss(0.0, 1.0))
                if margin_type == fcn.MARGIN_NORMAL:
                    draws.append(replay_rng.gauss(0.0, 1.0))
            context = (agent_id, market_id, call)
            assert upstream_rng.draws == [z.hex() for z in draws], context
            assert upstream_rng.getstate() == replay_rng.getstate(), context
            if not accessible:
                assert not orders, context
                counts["inaccessible"] += 1
                continue

            row = (now, fundamental, past, *weights, noise_scale, margin,
                   draws[0], draws[1] if len(draws) == 2 else 0.0,
                   window, effective, mean_reversion, margin_type, chart_sign)
            inputs.append(row)
            expected_orders.append(tuple(map(order_key, orders)))
            metadata.append(context)
            counts[f"margin_{margin_type}_chart_{chart_sign}"] += 1
            counts["normal_empty"] += bool(not orders and margin_type == fcn.MARGIN_NORMAL)
            counts["empty"] += not orders
            counts["time_zero"] += time == 0
            counts["window_zero"] += window == 0
            counts["mean_reversion_zero"] += mean_reversion == 0
            counts["unclipped_forecast"] += window > effective
    return np.array(inputs, dtype=INPUT_DTYPE), expected_orders, metadata, counts, order_module
