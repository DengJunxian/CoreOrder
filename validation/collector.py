"""Read-only instrumentation of unchanged PAMS methods.

Source inspected: PAMS 6cd5381 pams/logs/base.py and simulator.py.
No financial algorithm or numerical formula is copied here.
SPDX-License-Identifier: EPL-1.0
"""
from pams.logs import Logger
from pams.simulator import Simulator

from .codec import encode, snapshot


class TraceLogger(Logger):
    def __init__(self):
        super().__init__()
        self.events = []
        self.steps = []
        self.runner_rng = None
        self.stream = None
        self.sequence = 0

    def capture(self, log):
        session = getattr(self.simulator, "current_session", None)
        step = min((m.get_time() for m in self.simulator.markets), default=-1)
        self.record("events", {"event_seq": self.sequence, "session": getattr(session, "session_id", None),
                               "step": step, "type": type(log).__name__, "fields": encode(vars(log))})
        self.sequence += 1

    def record(self, channel, frame):
        stream = getattr(self, "stream", None)
        if stream is None:
            getattr(self, channel).append(frame)
        else:
            stream.emit(channel, frame)

    def state(self):
        stream = getattr(self, "stream", None)
        if stream is None:
            return {"state": snapshot(self.simulator, self.runner_rng)}
        state, words = stream.state(self.simulator, self.runner_rng)
        return {"state": state, "mt_words": words}

    def write(self, log):
        self.capture(log)
        super().write(log)

    def bulk_write(self, logs):
        for log in logs:
            self.capture(log)
        super().bulk_write(logs)

    def write_and_direct_process(self, log):
        self.capture(log)
        super().write_and_direct_process(log)

    def bulk_write_and_direct_process(self, logs):
        for log in logs:
            self.capture(log)
        super().bulk_write_and_direct_process(logs)

    def checkpoint(self):
        session = self.simulator.current_session
        self.record("steps", {"session": getattr(session, "session_id", None),
                              "next_market_times": [m.get_time() for m in self.simulator.markets],
                              **self.state()})


class ObservedSimulator(Simulator):
    def _update_times_on_markets(self, markets):
        # Run the original transition, including expiry, then observe all markets.
        super()._update_times_on_markets(markets)
        self.logger.checkpoint()
