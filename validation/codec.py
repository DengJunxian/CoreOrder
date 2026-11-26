"""Lossless semantic encoding; never use repr or object addresses in evidence.

SPDX-License-Identifier: EPL-1.0
"""
import hashlib
import json
import random

import numpy as np


def dumps(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(dumps(value).encode()).hexdigest()


def encode(value):
    from pams.order import Order, Cancel, OrderKind
    from pams.order_book import OrderBook
    if value is None or type(value) in (bool, int, str):
        return value
    if isinstance(value, (float, np.floating)):
        return {"float_hex": float(value).hex()}
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, random.Random):
        return {"python_random": encode(value.getstate())}
    if isinstance(value, np.random.Generator):
        return {"numpy_generator": encode(value.bit_generator.state)}
    if isinstance(value, np.ndarray):
        return {"ndarray": encode(value.tolist()), "dtype": value.dtype.str, "shape": list(value.shape)}
    if isinstance(value, OrderKind):
        return {"kind_id": value.kind_id, "name": value.name}
    if isinstance(value, (Order, Cancel)):
        return {"type": type(value).__name__, "fields": encode(vars(value))}
    if isinstance(value, OrderBook):
        # Sorting a COPY uses the upstream comparator and never mutates its heap.
        return {"type": "OrderBook", "fields": encode({
            **vars(value), "priority_queue": sorted(value.priority_queue)})}
    if isinstance(value, dict):
        if all(type(k) is str for k in value):
            return {k: encode(v) for k, v in sorted(value.items())}
        return {"map": sorted([[encode(k), encode(v)] for k, v in value.items()], key=lambda x: dumps(x[0]))}
    if isinstance(value, (list, tuple)):
        return [encode(x) for x in value]
    if isinstance(value, (set, frozenset)):
        return {"set": sorted([encode(x) for x in value], key=dumps)}
    for field in ("agent_id", "market_id", "session_id", "event_id"):
        if hasattr(value, field):
            return {"ref": field, "id": getattr(value, field)}
    if type(value).__name__ == "Simulator" or any(c.__name__ == "Simulator" for c in type(value).__mro__):
        return {"ref": "simulator"}
    if type(value).__name__ == "EventHook":
        return {"type": "EventHook", "fields": encode(vars(value))}
    if isinstance(value, type):
        return {"class": value.__module__ + "." + value.__qualname__}
    raise TypeError(f"Unsupported state type: {type(value).__module__}.{type(value).__qualname__}")


def fields(obj):
    # Backreferences and logger buffers are not business state. Unknown fields fail closed.
    return encode({k: v for k, v in vars(obj).items() if k not in ("simulator", "logger")})


def rng_states(simulator, runner_rng):
    owners = [("runner", runner_rng), ("simulator", simulator), ("fundamentals", simulator.fundamentals)]
    for group in ("agents", "markets", "sessions", "events"):
        owners.extend((f"{group}/{i}", obj) for i, obj in enumerate(getattr(simulator, group)))
    result = {}
    def visit(path, obj):
        if isinstance(obj, (random.Random, np.random.Generator)):
            result[path] = encode(obj)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                visit(path + "/" + dumps(encode(k)), v)
        elif isinstance(obj, (list, tuple)):
            for i, v in enumerate(obj):
                visit(path + "/" + str(i), v)
    for name, obj in owners:
        if isinstance(obj, random.Random):
            visit(name, obj)
        else:
            for key, value in vars(obj).items():
                visit(name + "/" + key, value)
    return result


def snapshot(simulator, runner_rng):
    return {
        "agents": [fields(x) for x in simulator.agents],
        "markets": [fields(x) for x in simulator.markets],
        "sessions": [fields(x) for x in simulator.sessions],
        "events": [fields(x) for x in simulator.events],
        "event_hooks": encode(simulator.event_hooks),
        "event_registry": encode(simulator.events_dict),
        "current_session": encode(simulator.current_session),
        "fundamentals": fields(simulator.fundamentals),
        "rng": rng_states(simulator, runner_rng),
    }
