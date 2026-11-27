import copy
import math
import random
import subprocess
import sys

import pytest

from validation.codec import encode, digest
from validation.compare import compare, first_diff, save_reproducer
from validation.invariants import check
from validation.reference import collect


@pytest.fixture(scope="module")
def trace(pams_root,small_config):
    return collect(small_config,101,pams_root)


def test_same_hash_does_not_hide_bit_fault(trace):
    bad=copy.deepcopy(trace)
    i=next(i for i,e in enumerate(bad["events"]) if e["type"]=="OrderLog")
    price=bad["events"][i]["fields"]["price"]
    price["float_hex"]=math.nextafter(float.fromhex(price["float_hex"]),math.inf).hex()
    assert bad["hashes"]==trace["hashes"]
    result=compare(trace,bad)
    assert result["status"]=="FAIL" and result["index"]==i
    assert result["difference"]["path"].endswith("/price/float_hex")


def test_swapped_events_and_replay(trace,tmp_path):
    bad=copy.deepcopy(trace)
    bad["events"][3],bad["events"][4]=bad["events"][4],bad["events"][3]
    bundle=tmp_path/"fault"
    result=save_reproducer(trace,bad,bundle)
    assert result["index"]==3
    run=subprocess.run([sys.executable,"-m","validation","replay","--bundle",str(bundle)],capture_output=True,text=True)
    assert run.returncode==1 and '"index": 3' in run.stdout


def test_missing_gauss_detected_without_orders(pams_root,small_config,monkeypatch):
    config=copy.deepcopy(small_config)
    # Identical expected/current price: real upstream still calls both normal gauss APIs.
    config["FCNAgents"].update(fundamentalWeight=1.0,chartWeight=0.0,noiseWeight=0.0,noiseScale=0.0,marginType="normal")
    good=collect(config,202,pams_root)
    original=random.Random.gauss
    skipped=[False]
    def omit_one(self,mu=0.0,sigma=1.0):
        if not skipped[0]:
            skipped[0]=True
            return 0.0  # deliberately no PRNG advancement: TEST FAULT ONLY
        return original(self,mu,sigma)
    monkeypatch.setattr(random.Random,"gauss",omit_one)
    bad=collect(config,202,pams_root)
    assert good["events"]==bad["events"]
    result=compare(good,bad)
    assert result["status"]=="FAIL" and result["scope"]=="steps"
    assert "python_random" in result["difference"]["path"]


def test_gauss_cache_and_numpy_state_are_material(trace):
    bad=copy.deepcopy(trace)
    bad["rng"]["agents/0/prng"]["python_random"][2]=encode(0.5)
    assert "python_random" in compare(trace,bad)["difference"]["path"]
    bad=copy.deepcopy(trace)
    bad["rng"]["fundamentals/_np_prng"]["numpy_generator"]["state"]["state"]+=1
    assert "numpy_generator" in compare(trace,bad)["difference"]["path"]


def test_conservation_and_execution_ledger(trace):
    assert check(trace)["status"]=="PASS"
    bad=copy.deepcopy(trace)
    bad["final"]["agents"][0]["cash_amount"]=encode(-1e9)
    assert check(bad)["status"]=="FAIL"


def test_upstream_thread_matches(pams_root,small_config,trace):
    candidate=collect(small_config,101,pams_root,"py-thread",2)
    assert compare(trace,candidate)["status"]=="PASS"


def test_heap_physical_order_not_semantic(pams_root):
    from pams.order import Order, LIMIT_ORDER
    from pams.order_book import OrderBook
    a,b=OrderBook(True),OrderBook(True)
    orders=[Order(i,0,True,LIMIT_ORDER,1,price=100-i,placed_at=0,order_id=i) for i in range(3)]
    a.priority_queue=orders
    b.priority_queue=[orders[0],orders[2],orders[1]]  # both legitimate heaps
    assert encode(a)==encode(b)
    assert encode(orders[0])!=encode(orders[1])


def test_strict_types_unknown_objects_and_seed_identity(trace):
    with pytest.raises(TypeError):
        encode(object())
    assert first_diff(1,True)["reason"]=="type"
    bad=copy.deepcopy(trace)
    bad["seed"]+=1
    assert compare(trace,bad)["scope"]=="identity"
