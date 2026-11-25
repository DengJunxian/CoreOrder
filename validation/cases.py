"""Small real PAMS configurations; not production optimization replacements.

SPDX-License-Identifier: EPL-1.0
"""
import copy
from .fixtures import small_config


def cases(pams_root):
    base=small_config(pams_root)
    result={}
    def add(name,config=None,quota=3):
        config=copy.deepcopy(base if config is None else config)
        for session in config["simulation"]["sessions"]:
            session["maxNormalOrders"]=quota
        result[name]=config
        return config
    add("C01a-M1",quota=1)
    normal=add("C01b-normal")
    normal["FCNAgents"]["marginType"]="normal"
    empty=add("C01c-all-empty")
    empty["FCNAgents"].update(fundamentalWeight=1.0,chartWeight=0.0,noiseWeight=0.0,noiseScale=0.0)
    sparse=add("C01d-sparse-access")
    sparse["Other"]=copy.deepcopy(sparse["Market"])
    sparse["simulation"]["markets"]=["Other","Market"]
    multi=add("C01e-four-markets")
    for name in ("M0","M1","M2","M3"):
        multi[name]=copy.deepcopy(multi["Market"])
    multi["simulation"]["markets"]=["M2","M0","M3","M1"]
    multi["FCNAgents"]["markets"]=["M0","M1","M2","M3"]
    add("C01f-M0",quota=0)
    add("C01f-MequalsN",quota=8)
    add("C01f-MaboveN",quota=12)
    mixed=add("C01c-mixed-empty")
    mixed["Empty"]=copy.deepcopy(mixed["FCNAgents"])
    mixed["Empty"].update(numAgents=4,markets=[])
    mixed["FCNAgents"]["numAgents"]=4
    mixed["simulation"]["agents"]=["Empty","FCNAgents"]
    hft=add("C01h-MarketMaker")
    hft["MM"]={"class":"MarketMakerAgent","numAgents":1,"markets":["Market"],
               "assetVolume":50,"cashAmount":10000,"targetMarket":"Market",
               "netInterestSpread":0.01,"orderTimeLength":1}
    hft["simulation"]["agents"].append("MM")
    for s in hft["simulation"]["sessions"]:
        s["maxHighFrequencyOrders"]=1
    event=add("C01g-fundamental-shock")
    event["Shock"]={"class":"FundamentalPriceShock","target":"Market","triggerTime":1,"priceChangeRate":0.05}
    event["simulation"]["sessions"][-1]["events"]=["Shock"]
    stopped=add("C01g-placement-stopped")
    stopped["simulation"]["sessions"][-1].update(withOrderPlacement=False,withOrderExecution=False)
    return result
