"""Read-only observations of the fixed PAMS runner and logger interfaces."""

import hashlib
from collections import Counter

from pams.agents.fcn_agent import FCNAgent
from pams.logs.base import CancelLog, ExecutionLog, ExpirationLog, Logger, MarketStepEndLog, OrderLog

from .config import json_bytes, sha256

EVENT_KIND = {
    OrderLog: "order",
    CancelLog: "cancel",
    ExpirationLog: "expiration",
    ExecutionLog: "execution",
}


def price_hex(value):
    return None if value is None else float(value).hex()


def accounts(simulator):
    return [
        {
            "agent_id": agent.agent_id,
            "cash_hex": price_hex(agent.get_cash_amount()),
            "holdings": agent.asset_volumes.copy(),
            **({"fcn": fcn_state(agent)} if type(agent) is FCNAgent else {}),
        }
        for agent in simulator.agents
    ]


def fcn_state(agent):
    return {
        "w_f": price_hex(agent.fundamental_weight),
        "w_c": price_hex(agent.chart_weight),
        "w_n": price_hex(agent.noise_weight),
        "noise_scale": price_hex(agent.noise_scale),
        "order_margin": price_hex(agent.order_margin),
        "window": agent.time_window_size,
        "mean_reversion": agent.mean_reversion_time,
        "margin_type": agent.margin_type,
        "chart_sign": 1 if agent.is_chart_following else -1,
    }


def market_state(market):
    return {
        "market_id": market.market_id,
        "name": market.name,
        "step": market.get_time(),
        "running": market.is_running,
        "market_price_hex": price_hex(market.get_market_price()),
        "fundamental_price_hex": price_hex(market.get_fundamental_price()),
        "last_executed_price_hex": price_hex(market.get_last_executed_price()),
        "best_buy_price_hex": price_hex(market.get_best_buy_price()),
        "best_sell_price_hex": price_hex(market.get_best_sell_price()),
        "executed_volume": market.get_executed_volume(),
    }


def ordered_book(book):
    return [
        {
            "agent_id": order.agent_id,
            "order_id": order.order_id,
            "order_kind": order.kind.name,
            "price_hex": price_hex(order.price),
            "placed_at": order.placed_at,
            "ttl": order.ttl,
            "volume": order.volume,
        }
        for order in sorted(book.priority_queue)
    ]


def final_state(simulator):
    return {
        "accounts": accounts(simulator),
        "markets": [
            {
                **market_state(market),
                "buy_book": ordered_book(market.buy_order_book),
                "sell_book": ordered_book(market.sell_order_book),
            }
            for market in simulator.markets
        ],
    }


def market_history(simulator):
    return [
        {
            "market_id": market.market_id,
            "market_prices_hex": [price_hex(value) for value in market.get_market_prices()],
            "fundamental_prices_hex": [price_hex(value) for value in market.get_fundamental_prices()],
            "last_executed_prices_hex": [price_hex(value) for value in market.get_last_executed_prices()],
            "mid_prices_hex": [price_hex(value) for value in market.get_mid_prices()],
            "executed_volumes": market.get_executed_volumes(),
        }
        for market in simulator.markets
    ]


def random_state(prng):
    version, state, gauss_next = prng.getstate()
    return {"version": version, "state": state, "gauss_next_hex": price_hex(gauss_next)}


def final_rng(runner):
    simulator = runner.simulator
    return {
        "runner": random_state(runner._prng),
        "simulator": random_state(simulator._prng),
        "fundamentals_python": random_state(simulator.fundamentals._prng),
        "fundamentals_numpy": simulator.fundamentals._np_prng.bit_generator.state,
        "markets": {m.market_id: random_state(m._prng) for m in simulator.markets},
        "agents": {a.agent_id: random_state(a.get_prng()) for a in simulator.agents},
        "sessions": {s.session_id: random_state(s.prng) for s in simulator.sessions},
        "events": {e.event_id: random_state(e.prng) for e in simulator.events},
    }


class WorkloadCounts(Logger):
    """Count existing PAMS logs in batches without reading their payloads."""

    def __init__(self):
        super().__init__()
        self.log_types = Counter()

    def __getstate__(self):
        state = vars(self).copy()
        state.pop("runner", None)
        return state

    def process(self, logs):
        self.log_types.update(map(type, logs))

    @property
    def counts(self):
        return {kind: self.log_types[cls] for cls, kind in EVENT_KIND.items()}

    @property
    def market_steps(self):
        return self.log_types[MarketStepEndLog]


class PamsObservations(Logger):
    def __init__(self, events, steps, step_states, run_id):
        super().__init__()
        self.events_file = events
        self.steps_file = steps
        self.step_states_file = step_states
        self.run_id = run_id
        self.event_digest = hashlib.sha256()
        self.event_seq = 0
        self.counts = Counter()
        self.market_steps = 0
        self.initial_accounts = None

    def __getstate__(self):
        # Upstream spawn copies the simulation graph. File handles and the
        # parent runner stay in the controlling process.
        parent_only = {"events_file", "steps_file", "step_states_file", "event_digest", "runner",
                       "events", "steps", "runner_rng"}
        return {key: value for key, value in vars(self).items() if key not in parent_only}

    def write(self, log):
        kind = EVENT_KIND.get(type(log))
        if kind is not None:
            fields = vars(log).copy()
            step = fields.pop("cancel_time" if kind == "cancel" else "time")
            if kind != "execution":
                fields["order_kind"] = fields.pop("kind").name
                fields["side"] = "buy" if fields.pop("is_buy") else "sell"
            for name in ("price", "buy_transaction_fee", "sell_transaction_fee"):
                if name in fields:
                    fields[name + "_hex"] = price_hex(fields.pop(name))
            session = self.simulator.current_session
            event = {
                **fields,
                "event_seq": self.event_seq,
                "session_id": session.session_id if session is not None else None,
                "step": step,
                "event_kind": kind,
            }
            self.event_digest.update(json_bytes(event))
            self.events_file.write(json_bytes({"run_id": self.run_id, **event}))
            self.event_seq += 1
            self.counts[kind] += 1
        super().write(log)

    def process_simulation_begin_log(self, log):
        self.initial_accounts = accounts(log.simulator)

    def process_market_step_end_log(self, log):
        row = {"run_id": self.run_id, "session_id": log.session.session_id, **market_state(log.market)}
        self.steps_file.write(json_bytes(row))
        self.market_steps += 1
        if log.market is log.simulator.markets[0]:
            # The upstream runner emits the first end-log after orders and before any after-step hook.
            state = {
                "run_id": self.run_id,
                "session_id": log.session.session_id,
                "step": log.market.get_time(),
                **final_state(log.simulator),
                "rng_hash": sha256(json_bytes(final_rng(self.runner))),
            }
            self.step_states_file.write(json_bytes(state))
