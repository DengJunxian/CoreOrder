"""P06 gate audit with a direct vendor reference and a gate-only collector."""
# SPDX-License-Identifier: EPL-1.0

import argparse
import difflib
import hashlib
import heapq
import inspect
import itertools
import json
import random
import subprocess
import sys
from collections import Counter
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / "vendor/pams"
sys.path.insert(0, str(VENDOR))

from pams import LIMIT_ORDER, MARKET_ORDER, Cancel, Market, Order
from pams.logs import CancelLog, ExecutionLog, ExpirationLog, Logger, OrderLog
from pams.order import OrderKind
from pams.runners import SequentialRunner

P05 = "2db0c2b9bed127b72119b83c6bf23293d5e5ee58"
PAMS = "6cd53810103780770c5b5d6ee0069ccab9f4b358"
C01_SEEDS = (101, 202, 303, 404, 505)
E_SHA = "b05d5555fa5cc756a91ab61c644e797ca227c26f"
E_CONFIG_DIR = "results/acceptance/E3/clean-52260be/matrix/configs"
HEAP_C01 = ("C01a-M1", "C01b-normal", "C01g-fundamental-shock")
SIDES = ("buy", "sell")
LOGS = (OrderLog, CancelLog, ExecutionLog, ExpirationLog)
MODES = ("upstream", "incremental")

# Workloads and edge operations from the EPL-1.0 distribution heap probe.
EDGES = {
    "partial_multi_level": [(False, 100.0, 3, 10, 1), (False, 101.0, 4, 10, 2),
                            (True, 102.0, 5, 10, 0), "execute"],
    "same_price_time_ties": [(False, 100.0, 2, 10, 1), (False, 100.0, 3, 10, 2),
                             (True, 100.0, 4, 10, 0), "execute"],
    "market_against_limit": [(False, 99.0, 2, 10, 1), (False, 101.0, 2, 10, 2),
                             (True, None, 3, 10, 0), "execute"],
    "equal_market_orders_with_limits": [(True, 98.0, 3, 10, 0), (False, 102.0, 3, 10, 1),
                                        (True, None, 2, 10, 0), (False, None, 2, 10, 1), "execute"],
    "unpriced_market_orders": [(True, None, 2, 10, 0), (False, None, 3, 10, 1), "execute"],
    "cancel_and_expire": [(False, 100.0, 3, 2, 1), (False, 101.0, 4, 3, 2),
                          (True, 102.0, 2, 4, 0), "execute", "cancel:1", "advance:4"],
    "noncrossing": [(True, 98.0, 3, 10, 0), (False, 102.0, 3, 10, 1), "execute"],
    "subsequent_crossings": [(False, 100.0, 3, 10, 1), (False, 101.0, 2, 10, 2),
                             (False, 105.0, 2, 10, 2), (True, 95.0, 3, 10, 0),
                             (True, 102.0, 4, 10, 0), "execute", (True, 104.0, 2, 10, 0),
                             "execute", (False, 95.0, 1, 10, 1), "execute"],
}


def canonical(value):
    if isinstance(value, float):
        return {"hex": value.hex()}
    if isinstance(value, OrderKind):
        return {"kind_id": value.kind_id, "name": value.name}
    if isinstance(value, dict):
        return {str(key): canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    if value is None or isinstance(value, (int, str)):
        return value
    raise TypeError(type(value))


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()


def encode(value):
    return json_bytes(canonical(value))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def order_sequence(queue):
    assert all(not order < queue[(i - 1) // 2] for i, order in enumerate(queue) if i)
    copy = queue.copy()
    popped = [heapq.heappop(copy) for _ in queue]
    assert [id(order) for order in popped] == [id(order) for order in sorted(queue)]
    assert len({order.order_id for order in popped}) == len(queue)
    return popped


class GateLogger(Logger):
    def __init__(self, trace):
        super().__init__()
        self.trace = trace
        self.counts = Counter()

    def emit(self, kind, payload):
        self.trace.write(encode({"seq": sum(self.counts.values()), "record_type": kind, **payload}))
        self.counts[kind] += 1

    def write(self, log):
        if type(log) in LOGS:
            session = self.simulator.current_session
            self.emit(type(log).__name__, {
                "session": None if session is None else session.session_id,
                **vars(log),
            })
        super().write(log)

    def rng(self):
        sim = self.simulator
        return {
            "runner": self.runner._prng.getstate(), "simulator": sim._prng.getstate(),
            "fundamentals_python": sim.fundamentals._prng.getstate(),
            "fundamentals_numpy": sim.fundamentals._np_prng.bit_generator.state,
            "agent": {a.agent_id: a.prng.getstate() for a in sim.agents},
            "market": {m.market_id: m._prng.getstate() for m in sim.markets},
            "session": {s.session_id: s.prng.getstate() for s in sim.sessions},
            "event": {e.event_id: e.prng.getstate() for e in sim.events},
        }

    def state(self, kind):
        markets = {}
        for market in self.simulator.markets:
            books = {}
            ids = set()
            for side in SIDES:
                book = getattr(market, f"{side}_order_book")
                sequence = order_sequence(book.priority_queue)
                assert ids.isdisjoint(order.order_id for order in sequence)
                ids.update(order.order_id for order in sequence)
                books[side] = {
                    "pop_order": [vars(order) for order in sequence],
                    "ttl_index": {key: [o.order_id for o in bucket]
                                  for key, bucket in book.expire_time_list.items()},
                }
            markets[market.market_id] = {
                "step": market.time, "running": market.is_running, "books": books,
                "market_price": market.get_market_price(),
                "fundamental_price": market.get_fundamental_price(),
                "mid_price": market.get_mid_price(),
                "last_executed_price": market.get_last_executed_price(),
                "executed_volume": market.get_executed_volume(),
            }
        self.emit(kind, {
            "markets": markets,
            "accounts": {a.agent_id: (a.cash_amount, a.asset_volumes) for a in self.simulator.agents},
            "rng_sha256": digest(encode(self.rng())),
        })

    def process_market_step_end_log(self, log):
        if log.market is self.simulator.markets[0]:
            self.state("step")

    def finish(self, output):
        self.state("final")
        methods = (
            "get_market_prices", "get_fundamental_prices", "get_mid_prices", "get_last_executed_prices",
            "get_executed_volumes", "get_executed_total_prices", "get_transaction_fee_revenues",
            "get_n_buy_orders", "get_n_sell_orders",
        )
        self.emit("history", {
            m.market_id: {name: getattr(m, name)() for name in methods}
            for m in self.simulator.markets
        })
        (output / "final_rng.json").write_bytes(encode(self.rng()))


@contextmanager
def instrument_heap():
    """Wrap real calls in a separate diagnostic run and check restored identity before fills."""
    report = {
        "restore_calls": 0, "heapq_calls": dict.fromkeys(("heapify", "heappush"), 0),
        "restore_order_lt_calls": dict.fromkeys(SIDES, 0),
        **{s: {"restore_calls": 0, "rows": []} for s in SIDES},
    }
    other_heapify = Counter()
    expected = {}
    current_operation = None
    original_lt = Order.__lt__
    original_collect = Market._collect_pending_executions
    original_execute = Market._execute_orders

    def wrap_heap(operation):
        original = getattr(heapq, operation)

        def call(queue, *args):
            nonlocal current_operation
            caller = sys._getframe(1).f_code.co_qualname
            if caller in ("Market._execution", "CoreOrderMarket._execution"):
                report["heapq_calls"][operation] += 1
                current_operation = operation
            elif operation == "heapify":
                other_heapify[caller] += 1
            try:
                return original(queue, *args)
            finally:
                current_operation = None

        return call

    def compare(left, right):
        if current_operation is not None:
            report["restore_order_lt_calls"]["buy" if left.is_buy else "sell"] += 1
        return original_lt(left, right)

    def collect(market, **popped):
        queues = [getattr(market, f"{side}_order_book").priority_queue for side in SIDES]
        before = [{id(o): encode(vars(o)) for o in queue} for queue in queues]
        pending, price = original_collect(market, **popped)
        if price is not None:
            report["restore_calls"] += 1
            for side, queue, members in zip(SIDES, queues, before):
                order_sequence(queue)
                removed = popped[f"popped_{side}_orders"]
                restored = [*queue, *removed]
                n, h, k = len(members), len(queue), len(removed)
                assert n == h + k
                assert {id(o): encode(vars(o)) for o in restored} == members
                report[side]["restore_calls"] += 1
                report[side]["rows"].append({
                    "market_id": market.market_id, "step": market.time, "heap_length_before": n,
                    "heap_length_remaining": h, "popped_count": k, "restore_fraction": k / max(n, 1),
                })
            expected[market.market_id] = before
        return pending, price

    def execute(market, price, volume, buy_order, sell_order):
        if market.market_id in expected:
            for side, members in zip(SIDES, expected.pop(market.market_id)):
                sequence = order_sequence(getattr(market, f"{side}_order_book").priority_queue)
                assert {id(o): encode(vars(o)) for o in sequence} == members
        return original_execute(market, price, volume, buy_order, sell_order)

    with ExitStack() as stack:
        for operation in ("heapify", "heappush"):
            stack.enter_context(patch.object(heapq, operation, wrap_heap(operation)))
        stack.enter_context(patch.object(Order, "__lt__", compare))
        stack.enter_context(patch.object(Market, "_collect_pending_executions", collect))
        stack.enter_context(patch.object(Market, "_execute_orders", execute))
        yield report, other_heapify
        assert not expected


def edge_run(runner, mode, operations, logger):
    runner._setup()
    sim = runner.simulator
    sim._update_times_on_markets(sim.markets)
    market = sim.markets[0]
    if mode == "incremental":
        market.book_restore = mode
    else:
        assert type(market) is Market
    market._is_running = True
    orders = []
    for op in operations:
        if op == "execute":
            sim._update_agents_for_execution(market._execution())
        elif op == "cancel:1":
            market._cancel_order(Cancel(order=orders[1]))
        elif op == "advance:4":
            for _ in range(4):
                sim._update_times_on_markets(sim.markets)
        else:
            side, price, volume, ttl, agent_id = op
            order = Order(agent_id=agent_id, market_id=0, is_buy=side, price=price,
                          kind=MARKET_ORDER if price is None else LIMIT_ORDER, volume=volume, ttl=ttl)
            market._add_order(order)
            orders.append(order)
        logger.state("edge")


def run(config, seed, mode, output, operations=None):
    output.mkdir()
    with (
        (output / "timeline.jsonl").open("wb") as trace,
        (output / "stdout.log").open("w") as stdout,
        (output / "stderr.log").open("w") as stderr,
        redirect_stdout(stdout), redirect_stderr(stderr),
    ):
        observer = GateLogger(trace)
        if mode == "upstream":
            runner = SequentialRunner(config, random.Random(seed), observer)
            observer.runner = runner
            if operations is None:
                runner.main()
                assert all(type(m) is Market for m in runner.simulator.markets)
            else:
                edge_run(runner, mode, operations, observer)
        else:
            from coreorder.config import incremental_workload
            from coreorder.market_adapter import CoreOrderMarket
            from coreorder.runner import run_py_seq

            settings = incremental_workload(json.loads(config.read_bytes()))
            effective = output / "effective_config.json"
            effective.write_text(json.dumps(settings), encoding="utf-8")
            if operations is None:
                runner, _ = run_py_seq(effective, seed, observer, book_restore=mode)
                observer.runner = runner
            else:
                runner = SequentialRunner(effective, random.Random(seed), observer)
                runner.class_register(CoreOrderMarket)
                observer.runner = runner
                edge_run(runner, mode, operations, observer)
            assert all(type(m) is CoreOrderMarket and m.book_restore == mode for m in runner.simulator.markets)
        observer.finish(output)
    return observer.counts


def first_field(a, b, path=()):
    if type(a) is not type(b):
        return list(path)
    if isinstance(a, dict):
        for key in sorted(a.keys() | b.keys()):
            if key not in a or key not in b:
                return [*path, key]
            difference = first_field(a[key], b[key], (*path, key))
            if difference is not None:
                return difference
    elif isinstance(a, list):
        for index, (left, right) in enumerate(itertools.zip_longest(a, b)):
            if index >= min(len(a), len(b)):
                return [*path, index]
            difference = first_field(left, right, (*path, index))
            if difference is not None:
                return difference
    elif a != b:
        return list(path)
    return None


def first_difference(a, b):
    for index, (x, y) in enumerate(itertools.zip_longest(a, b)):
        field = first_field(x, y)
        if field is not None:
            nearby = slice(max(0, index - 1), index + 2)
            return {"row": index, "field": field,
                    "reference_nearby": a[nearby], "candidate_nearby": b[nearby]}
    return None


def check_pair(folder, seed):
    reference, candidate = (folder / mode for mode in MODES)
    for filename in ("timeline.jsonl", "final_rng.json"):
        a, b = [(path / filename).read_bytes() for path in (reference, candidate)]
        if a != b:
            diff = first_difference(*([json.loads(line) for line in data.splitlines()] for data in (a, b)))
            (folder / "first_divergence.json").write_bytes(encode({
                **(diff or {"field": [], "reason": "canonical byte mismatch"}), "artifact": filename, "seed": seed,
                "config": str(folder / "workload.json"),
                "reference_rng": str(reference / "final_rng.json"), "candidate_rng": str(candidate / "final_rng.json"),
            }))
            raise AssertionError(folder / "first_divergence.json")


def probe_config(margin, ttl):
    config = json.loads((VENDOR / "samples/CI2002/config.json").read_bytes())
    config["FCNAgents"].update(numAgents=64, marginType=margin, timeWindowSize=list(ttl))
    for session, steps in zip(config["simulation"]["sessions"], (10, 50)):
        session.update(iterationSteps=steps, maxNormalOrders=16, withPrint=False)
    return config


def pair(root, label, config, seed, operations=None, *, diagnostic=False):
    folder = root / f"{label}-{seed}"
    folder.mkdir()
    workload = folder / "workload.json"
    workload.write_bytes(config)
    if operations is not None:
        (folder / "operations.json").write_text(json.dumps(operations) + "\n", encoding="utf-8")
    reports = {}
    for mode in MODES:
        if diagnostic:
            with instrument_heap() as (report, other):
                counts = run(workload, seed, mode, folder / mode, operations)
            reports[mode] = report
            (folder / mode / "heap_operations.json").write_bytes(
                json_bytes({**report, "other_heapify": other})
            )
        else:
            counts = run(workload, seed, mode, folder / mode, operations)
    check_pair(folder, seed)
    print(f"{folder.name} PASS {dict(counts)} workload={digest(config)} "
          f"timeline={digest((folder / 'upstream/timeline.jsonl').read_bytes())}", flush=True)
    return folder, reports


def compare_production_diagnostics(folder, reports, seed):
    for mode, expected in reports.items():
        output = folder / f"cli-{mode}"
        command = [sys.executable, "-m", "coreorder", "run", "--backend", "py-seq",
                   "--book-restore", mode, "--config", str(folder / "workload.json"),
                   "--seed", str(seed), "--output", str(output), "--heap-diagnostics", "--count-heap-comparisons"]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
        print(f"$ {command!r}\nexit={result.returncode}\n{result.stdout}{result.stderr}")
        assert result.returncode == 0
        actual = json.loads((output / "heap_diagnostics.json").read_bytes())
        if actual != expected:
            (folder / "first_diagnostic_difference.json").write_text(json.dumps({
                "mode": mode, "field": first_field(expected, actual), "expected": expected, "actual": actual,
            }, indent=2))
            raise AssertionError(folder / "first_diagnostic_difference.json")
    print("P05 CLI counters equal independent per-side rows and comparison counts in both modes.")


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def c01_config(name):
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "show", f"{E_SHA}:{E_CONFIG_DIR}/{name}.json"],
    )


def check_failure_report(source, output, seed):
    output.mkdir()
    (output / "workload.json").write_bytes((source / "workload.json").read_bytes())
    rows = [json.loads(line) for line in (source / "upstream/timeline.jsonl").read_bytes().splitlines()]
    index = next(i for i, row in enumerate(rows) if row["record_type"] == "OrderLog")
    modified = rows.copy()
    modified[index] = {**rows[index], "order_id": rows[index]["order_id"] + 1}
    for mode, timeline in zip(MODES, (rows, modified), strict=True):
        folder = output / mode
        folder.mkdir()
        (folder / "timeline.jsonl").write_bytes(b"".join(map(json_bytes, timeline)))
        (folder / "final_rng.json").write_bytes((source / mode / "final_rng.json").read_bytes())
    try:
        check_pair(output, seed)
    except AssertionError as error:
        report = output / "first_divergence.json"
        assert error.args == (report,)
    else:
        raise AssertionError("Injected order ID change must report a difference")
    details = json.loads(report.read_bytes())
    assert (details["row"], details["field"]) == (index, ["order_id"])
    print(f"First-difference self-test (injected order ID): row={index}, field=order_id, report={report}")


def verify_candidate(current):
    revision = git("rev-parse", "HEAD")
    assert git("-C", str(VENDOR), "rev-parse", "HEAD") == PAMS
    assert not git("-C", str(VENDOR), "status", "--porcelain")
    assert not git("status", "--porcelain")
    scope = "src/coreorder/market_adapter.py" if current else "src/coreorder"
    assert not git("diff", "--name-only", P05, "--", scope, "vendor", "requirements.lock", "UPSTREAM.lock.json")
    return revision if current else P05


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--current", action="store_true", help="re-run P06 checks on the current integrated candidate")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True)
    tested = verify_candidate(args.current)
    assert (VENDOR / "LICENSE").read_bytes() == (ROOT / "licenses/PAMS-EPL-1.0.txt").read_bytes()
    assert Path(inspect.getfile(Market)).resolve() == VENDOR / "pams/market.py"
    print(f"production_source={tested} audit_checkout={git('rev-parse', 'HEAD')} "
          f"pams={PAMS} license=EPL-1.0 interpreter={sys.version} reference={inspect.getfile(Market)}")

    from coreorder.market_adapter import CoreOrderMarket

    for name in ("remain_executable_orders", "_collect_pending_executions", "_get_execution_price",
                 "_execute_orders", "_add_order", "_cancel_order"):
        assert getattr(CoreOrderMarket, name) is getattr(Market, name), name
    diff = difflib.unified_diff(
        inspect.getsource(Market._execution).splitlines(),
        inspect.getsource(CoreOrderMarket._execution).splitlines(),
        fromfile="PAMS Market._execution", tofile="tested CoreOrderMarket._execution", lineterm="", n=2,
    )
    (output / "source.diff").write_text("\n".join(diff) + "\n", encoding="utf-8")

    for seed, margin, ttl in itertools.product((42, 20261125), ("fixed", "normal"), ((3, 6), (100, 200))):
        pair(output, f"probe-{margin}-{ttl[0]}-{ttl[1]}", json_bytes(probe_config(margin, ttl)), seed)
    fixtures = ROOT / "fixtures/pams"
    smoke = (fixtures / "ci2002-smoke/config.json").read_bytes()
    for label in HEAP_C01:
        config = c01_config(label)
        for seed in C01_SEEDS:
            pair(output, label, config, seed)
    edge_config = probe_config("fixed", (3, 6))
    edge_config["Market"]["tickSize"] = 1.0
    for name, ops in EDGES.items():
        folder, _ = pair(output, name, json_bytes(edge_config), 42, ops, diagnostic=name == "cancel_and_expire")
        if name == "cancel_and_expire":
            reports = [json.loads((folder / mode / "heap_operations.json").read_bytes()) for mode in MODES]
            for report in reports:
                assert report["other_heapify"] == {
                    "OrderBook.__init__": 2, "OrderBook._remove": 1, "OrderBook._check_expired_orders": 1,
                }
            print(f"Other heapify call sites in both modes: {reports[0]['other_heapify']}")

    folder, reports = pair(output, "heap-diagnostics", smoke, 42, diagnostic=True)
    plain, inc = (reports[m] for m in MODES)
    total_k = 0
    for side in SIDES:
        assert plain[side] == inc[side]
        rows = plain[side]["rows"]
        total_k += sum(r["popped_count"] for r in rows)
        print(f"{side} restore rows {json.dumps(rows)}")
    assert plain["restore_calls"] == inc["restore_calls"] > 0
    assert plain["heapq_calls"] == {"heapify": 2 * plain["restore_calls"], "heappush": 0}
    assert inc["heapq_calls"] == {"heapify": 0, "heappush": total_k}
    for mode, report in reports.items():
        print(f"{mode} heapq={report['heapq_calls']} comparisons={report['restore_order_lt_calls']}")
    compare_production_diagnostics(folder, reports, 42)
    check_failure_report(folder, output / "injected-order-id", 42)
    print("P06 local audit PASS: 8 probe pairs, 15 C01 representative pairs, 7 probe edges plus consecutive fills.")


if __name__ == "__main__":
    main()
