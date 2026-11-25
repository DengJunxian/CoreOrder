"""TEST FIXTURES ONLY: deliberate faults, never a production candidate backend.

SPDX-License-Identifier: EPL-1.0
"""
import argparse
import copy
import math
from pathlib import Path
import random
from unittest.mock import patch

from validation.compare import save_reproducer
from validation.fixtures import small_config
from validation.reference import collect


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--pams-root",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    config=small_config(a.pams_root)
    good=collect(config,101,a.pams_root)
    swapped=copy.deepcopy(good)
    swapped["events"][3],swapped["events"][4]=swapped["events"][4],swapped["events"][3]
    price_bit=copy.deepcopy(good)
    event=next(e for e in price_bit["events"] if e["type"]=="OrderLog")
    event["fields"]["price"]["float_hex"]=math.nextafter(float.fromhex(event["fields"]["price"]["float_hex"]),math.inf).hex()
    for name,bad in (("swapped-events",swapped),("price-bit",price_bit)):
        report=save_reproducer(good,bad,Path(a.output)/name)
        assert report["status"]=="FAIL"
        print(name,report["scope"],report["difference"]["path"])
    config["FCNAgents"].update(fundamentalWeight=1.0,chartWeight=0.0,noiseWeight=0.0,noiseScale=0.0,marginType="normal")
    good=collect(config,202,a.pams_root)
    original=random.Random.gauss
    skipped=[False]
    def omit_one(self,mu=0.0,sigma=1.0):
        if not skipped[0]:
            skipped[0]=True
            return 0.0
        return original(self,mu,sigma)
    with patch.object(random.Random,"gauss",omit_one):
        bad=collect(config,202,a.pams_root)
    assert good["events"]==bad["events"]
    report=save_reproducer(good,bad,Path(a.output)/"missing-gauss")
    assert report["status"]=="FAIL"
    print("missing-gauss",report["scope"],report["difference"]["path"])


if __name__=="__main__":
    main()
