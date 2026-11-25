"""Read-only observations of the fixed PAMS runner and logger interfaces."""

import hashlib
from collections import Counter

from pams.logs.base import CancelLog, ExecutionLog, ExpirationLog, Logger, OrderLog

from .config import json_bytes

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
        }
        for agent in simulator.agents
    ]


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


class PamsObservations(Logger):
    def __init__(self, events, steps, run_id):
        super().__init__()
        self.events_file = events
        self.steps_file = steps
        self.run_id = run_id
        self.event_digest = hashlib.sha256()
        self.event_seq = 0
        self.counts = Counter()
        self.market_steps = 0
        self.initial_accounts = None

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
