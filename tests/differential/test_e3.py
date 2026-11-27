import copy
import hashlib
import json
import random
from collections import Counter

import pytest

from validation.codec import encode,snapshot,dumps
from validation.gate import evaluate_cell
from validation.invariants import check
from validation.reference import collect


@pytest.mark.parametrize("scenario",["partial","ties","market-limit","double-market-limit","unpriced","cancel-expire","no-cross","continuous"])
def test_directed_real_pams(pams_root,small_config,scenario):
    from pams.runners import SequentialRunner
    from pams.order import Order,Cancel,LIMIT_ORDER,MARKET_ORDER
    from validation.collector import ObservedSimulator,TraceLogger
    logger=TraceLogger()
    runner=SequentialRunner(settings=copy.deepcopy(small_config),prng=random.Random(101),logger=logger,simulator_class=ObservedSimulator)
    logger.runner_rng=runner._prng
    runner._setup()
    sim=runner.simulator
    sim._update_times_on_markets(sim.markets)
    sim.current_session=sim.sessions[-1]
    market=sim.markets[0]
    market._is_running=True
    initial=snapshot(sim,runner._prng)
    def submit(agent,side,price,volume=1,ttl=2):
        order=Order(agent,0,side,MARKET_ORDER if price is None else LIMIT_ORDER,volume,price=price,ttl=ttl)
        runner._process_order(sim.current_session,order)
        return order
    if scenario=="partial":
        submit(0,True,101,3)
        submit(1,False,100)
        submit(2,False,99)
    elif scenario=="ties":
        submit(0,True,100)
        submit(1,True,100)
        submit(2,False,100,2)
        trades=[e["fields"]["buy_agent_id"] for e in logger.events if e["type"]=="ExecutionLog"]
        assert trades==[0,1]
    elif scenario=="market-limit":
        submit(0,True,None)
        submit(1,False,100)
    elif scenario=="double-market-limit":
        submit(0,True,None)
        submit(1,False,None)
        submit(2,False,100)
    elif scenario=="unpriced":
        submit(0,True,None)
        submit(1,False,None)
        assert not any(e["type"]=="ExecutionLog" for e in logger.events)
    elif scenario=="cancel-expire":
        order=submit(0,True,90,ttl=1)
        submit(1,False,110,ttl=1)
        runner._process_order(sim.current_session,Cancel(order))
        for _ in range(3):sim._update_times_on_markets(sim.markets)
        assert {e["type"] for e in logger.events}>={"CancelLog","ExpirationLog"}
    elif scenario=="no-cross":
        submit(0,True,90)
        submit(1,False,110)
        assert not any(e["type"]=="ExecutionLog" for e in logger.events)
    else:
        submit(0,True,100,2)
        submit(1,False,99)
        submit(2,False,100)
        submit(3,True,101)
        submit(4,False,101)
    final=snapshot(sim,runner._prng)
    # All operations above are real upstream methods. No heap optimization is defined here.
    trace={"initial":initial,"final":final,"events":logger.events,"steps":[]}
    assert check(trace)["status"]=="PASS"
    if scenario in ("partial","ties","market-limit","continuous"):
        assert any(e["type"]=="ExecutionLog" for e in logger.events)


def test_diagnostic_business_equivalence(pams_root,small_config,tmp_path):
    from experiments.diagnostic import run
    trace=collect(small_config,42,pams_root)
    low=run(small_config,42,pams_root)
    prof=run(small_config,42,pams_root,tmp_path/"test.prof")
    for candidate in (low,prof):
        assert candidate["final_hash"]==trace["hashes"]["final"]
        assert candidate["rng_hash"]==trace["hashes"]["rng"]
        assert candidate["event_counts"]==dict(Counter(e["type"] for e in trace["events"]))
        hasher=hashlib.sha256()
        for e in trace["events"]:hasher.update((dumps(e)+"\n").encode())
        assert candidate["event_stream_hash"]==hasher.hexdigest()
    assert low["measurement_mode"]!=prof["measurement_mode"]


def test_missing_and_fallback_never_pass(pams_root,small_config):
    reference=collect(small_config,42,pams_root)
    assert evaluate_cell(reference,None,None,None,{})["integration_status"]=="INTEGRATION_PENDING"
    manifest={"backend_requested":"native-parallel","backend_effective":"py-seq"}
    assert evaluate_cell(reference,reference,manifest,{"status":"PASS"},{})["status"]=="FAIL"
    assert evaluate_cell(reference,reference,manifest,{"status":"TIMEOUT"},{})["status"]=="TIMEOUT"
    from test_e1 import record
    manifest,_,_=record()
    manifest.update(input_hash=reference["input_hash"],seed=42)
    assert evaluate_cell(reference,reference,manifest,{"status":"PASS"},{"book_restore":"upstream"})["status"]=="PASS"
    del manifest["git_sha"]
    assert evaluate_cell(reference,reference,manifest,{"status":"PASS"},{})["status"]=="FAIL"


def test_negative_cash_is_upstream_legal(pams_root,small_config):
    config=copy.deepcopy(small_config)
    config["FCNAgents"]["cashAmount"]=-1000
    trace=collect(config,42,pams_root)
    assert check(trace)["status"]=="PASS"


def test_no_access_agents_have_empty_portfolios(pams_root,small_config):
    config=copy.deepcopy(small_config)
    config["FCNAgents"]["markets"]=[]
    trace=collect(config,101,pams_root)
    assert check(trace)["status"]=="PASS"
    assert not any(e["type"]=="OrderLog" for e in trace["events"])


def test_prefilled_gauss_cache_multiple_markets(pams_root):
    from pams.runners import SequentialRunner,MultiThreadAgentParallelRunner
    from validation.cases import cases
    from validation.collector import TraceLogger,ObservedSimulator
    from validation.compare import first_diff
    config=cases(pams_root)["C01e-four-markets"]
    config["FCNAgents"]["marginType"]="normal"
    config["simulation"]["numParallel"]=2
    results=[]
    for cls in (SequentialRunner,MultiThreadAgentParallelRunner):
        logger=TraceLogger()
        runner=cls(settings=copy.deepcopy(config),prng=random.Random(303),logger=logger,simulator_class=ObservedSimulator)
        logger.runner_rng=runner._prng
        runner._setup()
        for agent in runner.simulator.agents:
            state=agent.prng.getstate()
            agent.prng.setstate((state[0],state[1],0.375))
        runner._run()
        results.append((logger.events,logger.steps,snapshot(runner.simulator,runner._prng)))
    assert first_diff(results[0],results[1]) is None


@pytest.mark.parametrize("quota",[0,1])
def test_skipped_agents_rng_untouched(pams_root,small_config,quota):
    from pams.runners import SequentialRunner
    config=copy.deepcopy(small_config)
    runner=SequentialRunner(settings=config,prng=random.Random(404))
    runner._setup()
    runner.simulator._update_times_on_markets(runner.simulator.markets)
    session=runner.simulator.sessions[-1]
    session.max_normal_orders=quota
    before={a.agent_id:a.prng.getstate() for a in runner.simulator.agents}
    orders=runner._collect_orders_from_normal_agents(session)
    changed={a.agent_id for a in runner.simulator.agents if a.prng.getstate()!=before[a.agent_id]}
    assert len(orders)==quota
    assert changed==({orders[0][0].agent_id} if quota else set())


def test_command_timeout_is_preserved(tmp_path):
    import sys
    from experiments.capture import execute
    result=execute([sys.executable,"-c","import time; time.sleep(10)"],tmp_path/"timeout",0.15)
    assert result["status"]=="TIMEOUT" and result["censoring"]=="right"
    assert result["elapsed_s_driver"]<5  # must actually stop, not just label a completed sleep
