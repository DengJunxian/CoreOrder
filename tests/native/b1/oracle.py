"""Reference order output from the pinned, unmodified PAMS implementation."""

import hashlib
import sys
from pathlib import Path

PAMS_COMMIT = "6cd53810103780770c5b5d6ee0069ccab9f4b358"
FCN_SOURCE = Path("pams/agents/fcn_agent.py")
FCN_SHA256 = "e8b6d9b642042c0de25099ca41691923463c17a09e231c6c47ce1312ce825922"


def load_pams(source):
    source = source.resolve(strict=True)
    fcn_source = source / FCN_SOURCE
    actual = hashlib.sha256(fcn_source.read_bytes()).hexdigest()
    if actual != FCN_SHA256:
        raise ValueError(f"Unexpected FCN source SHA-256: {actual} ({fcn_source})")

    sys.path.insert(0, str(source))
    from pams.agents import fcn_agent
    from pams import market, order

    for module, relative_path in (
        (fcn_agent, FCN_SOURCE),
        (market, Path("pams/market.py")),
        (order, Path("pams/order.py")),
    ):
        if Path(module.__file__).resolve() != source / relative_path:
            raise RuntimeError(f"Unexpected import location: {module.__file__}")
    return fcn_agent, market, order


def order_key(order):
    return (
        order.agent_id, order.market_id, order.is_buy, order.kind.kind_id,
        order.volume, order.price.hex(), order.ttl, order.placed_at,
        order.order_id, order.is_canceled,
    )


def reference_orders(agent, market):
    return tuple(map(order_key, agent.submit_orders_by_market(market)))
