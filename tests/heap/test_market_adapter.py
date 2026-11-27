"""Controlled PAMS book states, with cases derived from the EPL-1.0 research probe."""

import heapq
import json
import random
from collections import Counter
from io import BytesIO
from traceback import extract_tb
from unittest.mock import patch

import pytest
from pams import LIMIT_ORDER, MARKET_ORDER, Cancel, Market, Order
from pams.runners import SequentialRunner

from coreorder.config import ROOT
from coreorder.market_adapter import CoreOrderMarket
from coreorder.snapshot import PamsObservations, WorkloadCounts, final_rng, final_state, market_history

BUY, SELL = True, False

# Add tuples hold side, price, volume and optional TTL. IDs follow submission order.
CASES = [
    ("partial_multi_level", [(SELL, 100, 3), (SELL, 101, 4), (BUY, 102, 5), "execute"],
     [(2, 0, 3, 101), (2, 1, 2, 101)]),
    ("same_price_time_ties", [(SELL, 100, 2), (SELL, 100, 3), (BUY, 100, 4), "execute"],
     [(2, 0, 2, 100), (2, 1, 2, 100)]),
    ("market_against_limit", [(SELL, 99, 2), (SELL, 101, 2), (BUY, None, 3), "execute"],
     [(2, 0, 2, 101), (2, 1, 1, 101)]),
    ("equal_market_orders_noncrossing_limits",
     [(BUY, 98, 3), (SELL, 102, 3), (BUY, None, 2), (SELL, None, 2), "execute"], []),
    ("unpriced_market_orders", [(BUY, None, 2), (SELL, None, 3), "execute"], []),
    ("cancel_and_expire", [(SELL, 100, 3, 2), (SELL, 101, 4, 3), (BUY, 102, 2, 4),
                           "execute", "cancel_second", "advance"], [(2, 0, 2, 100)]),
    ("noncrossing", [(BUY, 98, 3), (SELL, 102, 3), "execute"], []),
    ("subsequent_crossings", [(SELL, 100, 3), (SELL, 101, 2), (SELL, 105, 2),
                              (BUY, 95, 3), (BUY, 102, 4), "execute",
                              (BUY, 104, 2), "execute", (SELL, 95, 1), "execute"],
     [(4, 0, 3, 101), (4, 1, 1, 101), (5, 1, 1, 101), (5, 6, 1, 104)]),
]


def ready_market(market_class, book_restore):
    settings = json.loads((ROOT / "configs/workloads/smoke.json").read_bytes())
    settings["Market"].update({"class": market_class, "tickSize": 1.0})
    settings["FCNAgents"]["numAgents"] = 3
    events = BytesIO()
    observer = PamsObservations(events, BytesIO(), BytesIO(), "edge")
    runner = SequentialRunner(settings, prng=random.Random(42), logger=observer)
    observer.runner = runner
    runner._setup()
    runner.simulator._update_times_on_markets(runner.simulator.markets)
    market = runner.simulator.markets[0]
    if market_class is CoreOrderMarket:
        market.book_restore = book_restore
    market._is_running = True
    return runner, market, events


def add(market, orders, side, price, volume, ttl=10):
    order = Order(agent_id=len(orders) % 3, market_id=0, is_buy=side,
                  kind=MARKET_ORDER if price is None else LIMIT_ORDER,
                  volume=volume, price=price, ttl=ttl)
    market._add_order(order)
    orders.append(order)


def check_books(market, orders):
    sequences = []
    for book in (market.buy_order_book, market.sell_order_book):
        queue = book.priority_queue
        assert all(not order < queue[(index - 1) // 2] for index, order in enumerate(queue) if index)
        remaining = queue.copy()
        sequence = []
        while remaining:
            order = heapq.heappop(remaining)
            assert order is orders[order.order_id]
            sequence.append(order.order_id)
        assert sequence == [order.order_id for order in sorted(queue)]
        sequences.append(sequence)
    ids = sequences[0] + sequences[1]
    assert len(ids) == len(set(ids))
    return sequences


def edge(market_class, book_restore, operations):
    runner, market, events = ready_market(market_class, book_restore)
    simulator = runner.simulator
    orders, frames = [], []
    collect = market._collect_pending_executions
    execute_orders = market._execute_orders

    def check_after_collect(**kwargs):
        result = collect(**kwargs)
        check_books(market, orders)
        return result

    def check_before_fill(**kwargs):
        check_books(market, orders)
        for key, side in (("buy_order", market.buy_order_book), ("sell_order", market.sell_order_book)):
            assert any(order is kwargs[key] for order in side.priority_queue)
        return execute_orders(**kwargs)

    with (
        patch.object(market, "_collect_pending_executions", side_effect=check_after_collect),
        patch.object(market, "_execute_orders", side_effect=check_before_fill),
    ):
        for op in operations:
            if op == "execute":
                simulator._update_agents_for_execution(market._execution())
            elif op == "cancel_second":
                market._cancel_order(Cancel(order=orders[1]))
            elif op == "advance":
                for _ in range(4):
                    simulator._update_times_on_markets(simulator.markets)
            else:
                add(market, orders, *op)
            frames.append((check_books(market, orders), final_state(simulator)))

    rows = [json.loads(line) for line in events.getvalue().splitlines()]
    counts = WorkloadCounts()
    counts.bulk_write(runner.logger.pending_logs)
    counts._process()
    expected = Counter(row["event_kind"] for row in rows)
    assert counts.counts == {key: expected[key] for key in counts.counts}
    return rows, frames, market_history(simulator), final_rng(runner)


@pytest.mark.parametrize(("case", "operations", "fills"), CASES, ids=[case[0] for case in CASES])
def test_execution_edges(case, operations, fills):
    reference = edge(Market, "upstream", operations)
    assert edge(CoreOrderMarket, "upstream", operations) == reference
    assert edge(CoreOrderMarket, "incremental", operations) == reference
    events, frames, _, _ = reference
    assert [(e["buy_order_id"], e["sell_order_id"], e["volume"], float.fromhex(e["price_hex"]))
            for e in events if e["event_kind"] == "execution"] == fills
    if case == "cancel_and_expire":
        assert [(e["event_kind"], e["order_id"], e["step"]) for e in events[-2:]] == [
            ("cancel", 1, 0), ("expiration", 0, 3),
        ]
        assert frames[-1][0] == [[], []]


def test_no_price_assertion_still_precedes_restore():
    states = []
    for market_class, mode in ((Market, "upstream"), (CoreOrderMarket, "incremental")):
        runner, market, events = ready_market(market_class, mode)
        orders = []
        add(market, orders, BUY, None, 2)
        add(market, orders, SELL, None, 2)
        # Force entry past the guard to exercise the otherwise defensive no-price assertion.
        with patch.object(market, "remain_executable_orders", return_value=True):
            with pytest.raises(AssertionError) as failure:
                market._execution()
        origin = extract_tb(failure.value.__traceback__)[-1]
        assert (origin.name, origin.line) == ("_execution", "raise AssertionError")
        assert check_books(market, orders) == [[], []]
        states.append((events.getvalue(), final_state(runner.simulator), final_rng(runner)))
    assert states[0] == states[1]
