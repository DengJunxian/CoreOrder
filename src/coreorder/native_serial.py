"""PAMS normal-agent collection using the R4 native FCN kernel."""
# SPDX-License-Identifier: EPL-1.0
# Collection order derives from PAMS pams/runners/sequential.py at
# 6cd53810103780770c5b5d6ee0069ccab9f4b358. See licenses/PAMS-EPL-1.0.txt.

from importlib import import_module
from importlib.machinery import ExtensionFileLoader

from pams.agents.fcn_agent import FCNAgent, MARGIN_NORMAL
from pams.agents.market_maker_agent import MarketMakerAgent
from pams.market import Market
from pams.order import LIMIT_ORDER, Order
from pams.runners.sequential import SequentialRunner

from .contracts import CONTRACT_VERSION
from .packing import Draw, LayoutBuffer, pack_batch


def load_native_serial():
    try:
        module = import_module("_coreorder_fcn")
    except ImportError as error:
        raise NotImplementedError(
            "native backend requires the built _coreorder_fcn extension on PYTHONPATH"
        ) from error
    if (
        not isinstance(module.__spec__.loader, ExtensionFileLoader)
        or getattr(module, "contract_version", None) != CONTRACT_VERSION
    ):
        raise NotImplementedError("native backend requires the compiled R4-v1 FCN extension")
    return module


class DecisionBuffer(LayoutBuffer):
    def __init__(self, layout, evaluate):
        super().__init__(layout)
        self._evaluate_prefix = evaluate

    def packed(self, n, populate):
        def populate_or_check_prefix(writer):
            try:
                populate(writer)
            except ValueError:
                # shortcut: borrow D's written prefix until D exposes it on packing failure.
                # D advances _next only after writing and validating the entire row.
                # The failed batch is still exclusively held and never published.
                count = writer._next
                if count:
                    if self.layout == "aos":
                        prefix = self._columns["rows"][:count]
                    else:
                        prefix = {name: column[:count] for name, column in self._columns.items()}
                    self._evaluate_prefix(prefix)
                raise

        return super().packed(n, populate_or_check_prefix)


class NativeSerialRunner(SequentialRunner):
    def __init__(self, *, evaluate, layout="aos", market_adapter=None, **kwargs):
        super().__init__(**kwargs)
        self._evaluate = evaluate
        self._layout_buffer = DecisionBuffer(layout, evaluate)
        self._market_adapter = market_adapter
        self.agent_calls = 0
        self.native_rows = 0
        self.gauss_api_calls = 0
        self.batch_widths = []

    def _setup(self):
        super()._setup()
        if any(type(market) not in (Market, self._market_adapter) for market in self.simulator.markets):
            raise ValueError("native mode requires exact PAMS Market or the selected CoreOrderMarket adapter")
        if any(type(agent) is not FCNAgent for agent in self.simulator.normal_frequency_agents):
            raise ValueError("native mode requires exact PAMS FCNAgent for ordinary agents")
        if any(type(agent) is not MarketMakerAgent for agent in self.simulator.high_frequency_agents):
            raise ValueError("native mode supports only the original MarketMakerAgent HFT path")

    def _collect_orders_from_normal_agents(self, session):
        agents = self.simulator.normal_frequency_agents
        agents = self._prng.sample(agents, len(agents))
        markets = self.simulator.markets
        all_orders = []
        offset = 0
        while offset < len(agents) and len(all_orders) < session.max_normal_orders:
            remaining = session.max_normal_orders - len(all_orders)
            batch_agents = agents[offset:offset + remaining]
            first_call = self.agent_calls
            orders_by_agent = self._evaluate_batch(batch_agents, markets, first_call)
            self.agent_calls += len(batch_agents)
            self.batch_widths.append(len(batch_agents))
            offset += len(batch_agents)
            for agent, orders in zip(batch_agents, orders_by_agent, strict=True):
                if orders:
                    if not session.with_order_placement:
                        raise AssertionError("currently order is not accepted")
                    self._check_submitted_orders(agent=agent, orders=orders)
                    all_orders.append(orders)
        return all_orders

    def _evaluate_batch(self, agents, markets, first_call):
        draws = []
        for agent in agents:
            for market in markets:
                if not agent.is_market_accessible(market.market_id):
                    continue
                noise = agent.prng.gauss(mu=0.0, sigma=1.0)
                margin = agent.prng.gauss(mu=0.0, sigma=1.0) if agent.margin_type == MARGIN_NORMAL else None
                draws.append(Draw(agent.agent_id, market.market_id, noise, margin))
                self.gauss_api_calls += 1 + (margin is not None)

        orders_by_agent = [[] for _ in agents]
        with pack_batch(
            self._layout_buffer, agents, markets, draws,
            first_call=first_call, market_adapter=self._market_adapter,
        ) as batch:
            outputs = self._evaluate(batch.inputs)
            self.native_rows += len(batch.metadata)
            for output, metadata, window in zip(outputs, batch.metadata, batch.inputs["window"], strict=True):
                side = int(output["side"])
                if side:
                    agent_id, market_id, call_index = map(int, metadata)
                    orders_by_agent[call_index - first_call].append(Order(
                        agent_id=agent_id, market_id=market_id, is_buy=side > 0,
                        kind=LIMIT_ORDER, volume=1, price=float(output["price"]),
                        ttl=int(window),
                    ))
        return orders_by_agent
