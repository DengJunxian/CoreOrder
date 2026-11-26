"""Independent conservation and event/book/ledger consistency on no-fee fixtures.

These are supplementary properties, not a replacement for exact differential tests.
SPDX-License-Identifier: EPL-1.0
"""
import math


def number(value):
    return float.fromhex(value["float_hex"]) if isinstance(value, dict) else value


def assets(agent):
    value=agent["asset_volumes"]
    return dict(value["map"]) if value else {}


def totals(state):
    cash = math.fsum(number(a["cash_amount"]) for a in state["agents"])
    securities = {}
    for agent in state["agents"]:
        for market, volume in assets(agent).items():
            securities[market] = securities.get(market, 0) + volume
    return cash, securities


def check(trace, abs_tol=1e-7, rel_tol=1e-12):
    baseline_cash, baseline_assets = totals(trace["initial"])
    failures = []
    states = [(f"step/{i}", row["state"]) for i,row in enumerate(trace["steps"])] + [("final",trace["final"])]
    for label, state in states:
        cash, holdings = totals(state)
        if not math.isclose(cash, baseline_cash, abs_tol=abs_tol, rel_tol=rel_tol):
            failures.append({"path":label+"/cash", "initial":baseline_cash,"actual":cash})
        if holdings != baseline_assets:
            failures.append({"path":label+"/assets", "initial":baseline_assets,"actual":holdings})
    expected = {a["agent_id"]: {"cash":number(a["cash_amount"]), "assets":assets(a)} for a in trace["initial"]["agents"]}
    live = {}
    for i,event in enumerate(trace["events"]):
        f, kind = event["fields"], event["type"]
        market = f.get("market_id")
        if kind == "OrderLog":
            key = (market,f["order_id"])
            if key in live or f["volume"] <= 0:
                failures.append({"path":f"events/{i}","reason":"duplicate/nonpositive order"})
            live[key] = dict(f)
        elif kind == "ExecutionLog":
            volume, price = f["volume"], number(f["price"])
            if volume <= 0 or not math.isfinite(price):
                failures.append({"path":f"events/{i}","reason":"invalid execution"})
            if any(number(f.get(side+"_transaction_fee",0)) != 0 for side in ("buy","sell")):
                raise ValueError("Fee-aware conservation is not in this validator's declared support")
            for side, sign in (("buy",1),("sell",-1)):
                key = (market,f[side+"_order_id"])
                order = live.get(key)
                if (order is None or order["volume"] < volume or order["is_buy"] != (side=="buy")
                        or order["agent_id"] != f[side+"_agent_id"]):
                    failures.append({"path":f"events/{i}/{side}","reason":"execution/order inconsistency"})
                if order is not None:
                    order["volume"] -= volume
                    if order["volume"] == 0:
                        del live[key]
                account = expected[f[side+"_agent_id"]]
                account["cash"] -= sign*price*volume
                account["assets"][market] += sign*volume
        elif kind in ("CancelLog","ExpirationLog"):
            live.pop((market,f["order_id"]),None)
    final_books = {}
    for market in trace["final"]["markets"]:
        for side in ("buy","sell"):
            for order in market[side+"_order_book"]["fields"]["priority_queue"]:
                f=order["fields"]
                final_books[(f["market_id"],f["order_id"])] = f
    if set(live) != set(final_books) or any(live[k]["volume"] != final_books[k]["volume"] for k in set(live)&set(final_books)):
        failures.append({"path":"final/books","reason":"event residual differs from book"})
    for a in trace["final"]["agents"]:
        account=expected[a["agent_id"]]
        if not math.isclose(account["cash"],number(a["cash_amount"]),abs_tol=abs_tol,rel_tol=rel_tol) or account["assets"]!=assets(a):
            failures.append({"path":f"final/agents/{a['agent_id']}","reason":"execution ledger mismatch"})
    return {"status":"FAIL" if failures else "PASS", "failures":failures,
            "cash_tolerance":{"abs":abs_tol,"rel":rel_tol}, "scope":"no-fee conservation and event-ledger-book consistency"}
