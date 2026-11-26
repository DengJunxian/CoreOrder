"""Member D's packing tests with genuine PAMS classes, independent of the runner."""

import hashlib
import json
import os
import random
import unittest
from pathlib import Path

from pams.agents.fcn_agent import FCNAgent, MARGIN_FIXED, MARGIN_NORMAL
from pams.market import Market

from coreorder.packing import Draw, LayoutBuffer, pack_batch


def make_agent(agent_id, market_ids, margin, window):
    agent = FCNAgent(agent_id, random.Random(2026 + agent_id), None, str(agent_id))
    agent.setup(
        dict(cashAmount=1000, assetVolume=3, fundamentalWeight=1.25,
             chartWeight=2.5, noiseWeight=0.5, noiseScale=0.001,
             orderMargin=0.02, meanReversionTime=2, timeWindowSize=window,
             marginType=margin),
        accessible_markets_ids=market_ids,
    )
    return agent


def make_market(market_id, prices, fundamental):
    market = Market(market_id, random.Random(42 + market_id), None, str(market_id))
    market.setup(dict(tickSize=0.1, marketPrice=prices[0]))
    for value in prices:
        market._update_time(next_fundamental_price=fundamental)
        # Seed an explicit market-price history without instantiating a runner.
        market._market_prices[market.get_time()] = value
    return market


class PackingWithPams(unittest.TestCase):
    def collect_draws(self, agents, markets):
        """Replay the upstream calls on an independent PRNG stream for verification."""
        draws = []
        for agent in agents:
            reference = random.Random()
            reference.setstate(agent.prng.getstate())
            for market in markets:
                orders = agent.submit_orders_by_market(market)
                if agent.is_market_accessible(market.market_id):
                    noise = reference.gauss(0, 1)
                    margin = reference.gauss(0, 1) if agent.margin_type == MARGIN_NORMAL else None
                    draws.append(Draw(agent.agent_id, market.market_id, noise, margin))
                if agent.time_window_size == 0:
                    self.assertEqual(orders, [])
                self.assertEqual(reference.getstate(), agent.prng.getstate())
        return draws

    def test_sparse_access_live_updates_and_rng(self):
        for layout in ("aos", "soa"):
            with self.subTest(layout=layout):
                buffer = LayoutBuffer(layout)
                markets = [make_market(8, [91.0, 93.0, 98.0], 101.0),
                           make_market(3, [111.0, 114.0, 108.0], 109.0)]
                fixed = make_agent(9, [3], "fixed", 8)
                empty = make_agent(6, [], "normal", 1)
                normal = make_agent(2, [8, 3], "normal", 0)
                normal.prng.gauss(0, 1)  # Start with a populated Gaussian cache.
                agents = [fixed, empty, normal]
                for iteration in range(2):
                    if iteration:
                        normal.time_window_size = 1
                        normal.is_chart_following = False
                        normal.fundamental_weight = 4.75
                        normal.order_margin = 0.003
                        markets[0]._update_time(next_fundamental_price=131.0)
                        markets[0]._market_prices[3] = 121.0
                    draws = self.collect_draws(agents, markets)
                    states = [a.prng.getstate() for a in agents]
                    with pack_batch(buffer, agents, markets, draws, first_call=7) as view:
                        self.assertEqual(view.metadata.tolist(), [(9, 3, 7), (2, 8, 9), (2, 3, 9)])
                        fields = view.inputs
                        self.assertEqual(fields["window"].tolist(), [8, iteration, iteration])
                        self.assertEqual(fields["effective_window"].tolist(), [2, iteration, iteration])
                        self.assertEqual(fields["p_then"].tolist(), [111, 98, 114 if iteration else 108])
                        self.assertEqual(fields["p_now"].tolist(), [108, 121 if iteration else 98, 108])
                        self.assertEqual(fields["p_fund"].tolist(), [109, 131 if iteration else 101, 109])
                        self.assertEqual(fields["margin_type"].tolist(), [MARGIN_FIXED, MARGIN_NORMAL, MARGIN_NORMAL])
                        self.assertEqual(fields["w_f"].tolist(), [1.25, normal.fundamental_weight, normal.fundamental_weight])
                        self.assertEqual(fields["chart_sign"].tolist(), [1, 1 - 2*iteration, 1 - 2*iteration])
                        self.assertEqual(fields["order_margin"].tolist(), [fixed.order_margin, normal.order_margin, normal.order_margin])
                        self.assertEqual(fields["z_noise"].tolist(), [draw.z_noise for draw in draws])
                        self.assertEqual(fields["z_margin"].tolist(), [0.0, draws[1].z_margin, draws[2].z_margin])
                    self.assertEqual(states, [a.prng.getstate() for a in agents])

    def test_invalid_sample_stream_and_recovery(self):
        market = make_market(3, [111.0], 113.0)
        fixed = make_agent(9, [3], "fixed", 4)
        normal = make_agent(2, [3], "normal", 1)
        first, second = self.collect_draws([fixed, normal], [market])
        bad_batches = [
            ([first], "missing sample"),
            ([second, first], "expected sample"),
            ([first, second, second], "trailing samples"),
            ([Draw(9, 3, 0.0, 1.0), second], "number of gauss samples"),
            ([first, Draw(2, 3, 0.0)], "number of gauss samples"),
            ([first, Draw(2, 3, float("nan"), -1.0)], "non-finite"),
        ]
        for layout in ("aos", "soa"):
            buffer = LayoutBuffer(layout)
            for samples, reason in bad_batches:
                with self.subTest(layout=layout, reason=reason):
                    with self.assertRaisesRegex(ValueError, reason):
                        with pack_batch(buffer, [fixed, normal], [market], samples):
                            self.fail("published partial or invalid rows")
                    with self.assertRaises(RuntimeError):
                        with buffer.read():
                            self.fail("invalid batch visible to later reader")
            normal.margin_type = -1
            with self.assertRaisesRegex(ValueError, "unknown margin"):
                with pack_batch(buffer, [fixed, normal], [market], [first, second]):
                    self.fail("unknown margin reached consumer")
            normal.margin_type = MARGIN_NORMAL
            with pack_batch(buffer, [fixed, normal], [market], [first, second]) as view:
                self.assertEqual(view.metadata.tolist(), [(9, 3, 0), (2, 3, 1)])
            blocked = make_agent(88, [], "fixed", 1)
            with pack_batch(buffer, [blocked], [market], []) as view:
                self.assertEqual(len(view.metadata), 0)
                self.assertEqual(len(view.inputs["p_now"]), 0)

    def test_rejects_agents_with_untrusted_behavior(self):
        class SideEffectAgent(FCNAgent):
            def is_market_accessible(self, market_id):
                raise AssertionError("packer ran untrusted subclass code")

        agent = SideEffectAgent(55, random.Random(55), None, "custom")
        market = make_market(3, [101.0], 103.0)
        for layout in ("aos", "soa"):
            with self.assertRaises(TypeError):
                with pack_batch(LayoutBuffer(layout), [agent], [market], []):
                    self.fail("custom policy reached consumer")

    def test_pack_from_public_fixture(self):
        # Default to the path after A's fixture lands in main.
        default = Path(__file__).resolve().parents[2] / "fixtures" / "pams"
        root = Path(os.environ.get("COREORDER_PAMS_FIXTURE", default))
        if not root.exists():
            self.skipTest("set COREORDER_PAMS_FIXTURE to A's fixtures/pams directory")
        raw = (root / "fcn" / "rows.jsonl").read_bytes()
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["pams_sha"], "6cd53810103780770c5b5d6ee0069ccab9f4b358")
        self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest["files"]["fcn/rows.jsonl"])
        entries = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual(len(entries), 24)
        for layout in ("aos", "soa"):
            buffer = LayoutBuffer(layout)
            for entry in entries:
                row = {k: float.fromhex(v) if isinstance(v, str) else v
                       for k, v in entry["input"].items()}
                aid, mid, seq = (entry[key] for key in ("agent_id", "market_id", "call_index"))
                with self.subTest(layout=layout, workload=entry["workload"], call=seq):
                    agent = make_agent(aid, [mid], entry["workload"], row["window"])
                    agent.fundamental_weight = row["w_f"]
                    agent.chart_weight = row["w_c"]
                    agent.noise_weight = row["w_n"]
                    agent.noise_scale = row["noise_scale"]
                    agent.order_margin = row["order_margin"]
                    agent.mean_reversion_time = row["mean_reversion"]
                    agent.is_chart_following = row["chart_sign"] == 1
                    prices = [row["p_then"]] * (entry["step"] + 1)
                    prices[-1] = row["p_now"]
                    market = make_market(mid, prices, row["p_fund"])
                    sample = Draw(aid, mid, row["z_noise"], row["z_margin"] if row["margin_type"] else None)
                    state = agent.prng.getstate()
                    with pack_batch(buffer, [agent], [market], [sample], first_call=seq) as view:
                        self.assertEqual(view.metadata.tolist(), [(aid, mid, seq)])
                        for field, expected in row.items():
                            actual = view.inputs[field][0].item()
                            if isinstance(expected, float):
                                self.assertEqual(actual.hex(), expected.hex(), field)
                            else:
                                self.assertEqual(actual, expected, field)
                    self.assertEqual(agent.prng.getstate(), state)
