"""Optional, thread-local observation of the two serial restoration paths."""

import heapq
import sys
from contextlib import contextmanager

from pams import Market, Order

from .market_adapter import CoreOrderMarket

EXECUTION_CODE = (Market._execution.__code__, CoreOrderMarket._execution.__code__)
COLLECT_CODE = Market._collect_pending_executions.__code__
COMPARE_CODE = Order.__lt__.__code__
SIDES = ("buy", "sell")


class HeapDiagnostics:
    def __init__(self, *, sizes: bool, comparisons: bool):
        self.sizes = sizes
        self.comparisons = comparisons
        self.rows = {side: [] for side in SIDES}
        self.heapq_calls = {"heapify": 0, "heappush": 0}
        self.order_lt_calls = dict.fromkeys(SIDES, 0)
        self._before = ()

    @contextmanager
    def capture(self):
        previous = sys.getprofile()
        sys.setprofile(self._observe)
        try:
            yield
        finally:
            sys.setprofile(previous)

    def _observe(self, frame, event, arg):
        code = frame.f_code
        if self.sizes and code is COLLECT_CODE:
            if event == "call":
                market = frame.f_locals["self"]
                self._before = (len(market.buy_order_book), len(market.sell_order_book))
            elif event == "return" and arg is not None and arg[1] is not None:
                values = frame.f_locals
                market = values["self"]
                for index, side in enumerate(SIDES):
                    n = self._before[index]
                    h = len(getattr(market, f"{side}_order_book"))
                    k = len(values[f"popped_{side}_orders"])
                    if n != h + k:
                        raise AssertionError(f"{side} heap: {n=} != {h=} + {k=}")
                    self.rows[side].append({
                        "market_id": market.market_id, "step": market.time,
                        "heap_length_before": n, "popped_count": k,
                        "heap_length_remaining": h, "restore_fraction": k / max(n, 1),
                    })
        elif self.sizes and code in EXECUTION_CODE and event == "c_return":
            if arg is heapq.heapify or arg is heapq.heappush:
                self.heapq_calls[arg.__name__] += 1
        elif self.comparisons and code is COMPARE_CODE and event == "call":
            # CPython's C heap operations leave _execution as the Python caller.
            if frame.f_back is not None and frame.f_back.f_code in EXECUTION_CODE:
                side = "buy" if frame.f_locals["self"].is_buy else "sell"
                self.order_lt_calls[side] += 1

    def report(self):
        result = {}
        if self.sizes:
            result.update(restore_calls=len(self.rows["buy"]), heapq_calls=self.heapq_calls)
            for side, rows in self.rows.items():
                result[side] = {"restore_calls": len(rows), "rows": rows}
        if self.comparisons:
            result["restore_order_lt_calls"] = self.order_lt_calls
        return result
