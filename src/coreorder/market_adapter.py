# SPDX-License-Identifier: EPL-1.0
# _execution derives from PAMS pams/market.py at 6cd53810103780770c5b5d6ee0069ccab9f4b358.
# PAMS contributors retain their rights. See licenses/PAMS-EPL-1.0.txt.

import heapq
from typing import cast

from pams import Market, Order
from pams.logs.base import ExecutionLog


class CoreOrderMarket(Market):
    book_restore = "upstream"

    def _execution(self) -> list[ExecutionLog]:
        if self.book_restore == "upstream":
            return super()._execution()
        if self.book_restore != "incremental":
            raise ValueError(f"unknown book_restore mode: {self.book_restore!r}")

        if not self.remain_executable_orders():
            return []
        popped_buy_orders: list[Order] = []
        popped_sell_orders: list[Order] = []
        pending, price = self._collect_pending_executions(
            popped_buy_orders=popped_buy_orders, popped_sell_orders=popped_sell_orders
        )
        if price is None:
            raise AssertionError
        # Collect only pops roots, leaving both remaining queues as heaps.
        for order in popped_buy_orders:
            heapq.heappush(self.buy_order_book.priority_queue, order)
        for order in popped_sell_orders:
            heapq.heappush(self.sell_order_book.priority_queue, order)
        logs: list[ExecutionLog] = [
            self._execute_orders(
                price=cast(float, price), volume=x[0], buy_order=x[1], sell_order=x[2]
            )
            for x in pending
        ]
        if self.remain_executable_orders():
            raise AssertionError
        return logs
