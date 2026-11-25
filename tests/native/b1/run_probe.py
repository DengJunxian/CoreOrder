"""Original PAMS functions are the oracle; no full-market performance claim.

The native numerical expression is an EPL-1.0 adaptation. This driver creates
valid market states and calls the actual FCNAgent.submit_orders_by_market.
"""
import argparse
import collections
import hashlib
import importlib.metadata
import json
import pathlib
import platform
import random
import sys
import warnings

import numpy as np

from oracle import FCN_SHA256, PAMS_COMMIT, load_pams, order_key, reference_orders

root = pathlib.Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser()
parser.add_argument('--pams-source', type=pathlib.Path, default=root / 'vendor/pams')
parser.add_argument('--native-module-dir', type=pathlib.Path, required=True)
args=parser.parse_args()
fcn, market_module, order_module = load_pams(args.pams_source)
FCNAgent, MARGIN_FIXED, MARGIN_NORMAL = fcn.FCNAgent, fcn.MARGIN_FIXED, fcn.MARGIN_NORMAL
Market = market_module.Market
Order, LIMIT_ORDER = order_module.Order, order_module.LIMIT_ORDER
module_dir = args.native_module_dir.resolve(strict=True)
sys.path.insert(0, str(module_dir))
import fcn_probe

if pathlib.Path(fcn_probe.__file__).resolve().parent != module_dir:
    raise RuntimeError(f'Unexpected native module location: {fcn_probe.__file__}')


class ObservedRandom(random.Random):
    def __init__(self, seed):
        super().__init__(seed)
        self.gauss_calls = 0

    def gauss(self, mu=0.0, sigma=1.0):
        self.gauss_calls += 1
        return super().gauss(mu=mu, sigma=sigma)


warnings.filterwarnings('ignore',message='price should be positive')
maker=random.Random(20261125)
rows=[]
oracle=[]
metadata=[]
counts=collections.Counter()
rng_mismatches=[]

for ai in range(100):
    r1=ObservedRandom(700001+ai)
    r2=random.Random(700001+ai)
    if ai%2:
        r1.gauss(0.0,1.0)
        r2.gauss(0.0,1.0)
        counts['agents_initial_gauss_cache_nonempty']+=1
    agent=FCNAgent(ai,r1,None,'probe-'+str(ai))
    for j in range(100):
        market_id=1+j%3
        accessible=(ai+j)%11!=0
        time=[0,1,7,30,80][(ai+j)%5]
        window=[0,1,5,20,80][(ai*3+j)%5]
        current=maker.uniform(100.0,5000.0)
        fundamental=current*maker.uniform(0.98,1.02)
        past=current*maker.uniform(0.98,1.02)
        noise_scale=maker.uniform(0.0,0.005)
        equality=(ai+j)%13==0
        if equality:
            fundamental=current; past=current; noise_scale=0.0
        if min(time,window)==0:
            past=current
        mean_reversion=max(window,1)
        if (ai+j)%17==0:
            mean_reversion=0; fundamental=current
        weights=[maker.uniform(0.1,5.0) for _ in range(3)]
        chart_sign=1 if ((ai+3*j)//2)%2 else -1
        margin_type=MARGIN_FIXED if (ai+j)%2 else MARGIN_NORMAL
        margin=maker.uniform(0.0,0.2)
        if (ai+j)%37==0 and margin_type==MARGIN_FIXED:
            margin=1.0
        agent.asset_volumes={market_id:100} if accessible else {}
        agent.fundamental_weight,agent.chart_weight,agent.noise_weight=weights
        agent.noise_scale=noise_scale
        agent.time_window_size=window
        agent.mean_reversion_time=mean_reversion
        agent.is_chart_following=chart_sign==1
        agent.margin_type=margin_type
        agent.order_margin=margin
        market=Market(market_id,random.Random(42),None,'probe-market')
        market.time=time
        market._market_prices=[past]*(time+1)
        market._market_prices[-1]=current
        market._fundamental_prices=[fundamental]*(time+1)
        calls_before = r1.gauss_calls
        original = reference_orders(agent, market)
        g1=r2.gauss(0.0,1.0) if accessible else 0.0
        g2=r2.gauss(0.0,1.0) if accessible and margin_type==MARGIN_NORMAL else 0.0
        expected_calls = (1 + int(margin_type == MARGIN_NORMAL)) if accessible else 0
        actual_calls = r1.gauss_calls - calls_before
        states_match = r1.getstate() == r2.getstate()
        if not states_match or actual_calls != expected_calls:
            rng_mismatches.append({'agent': ai, 'call': j, 'states_match': states_match,
                                   'expected_calls': expected_calls, 'actual_calls': actual_calls})
        if not accessible:
            counts['inaccessible_no_rng_consumption']+=1
        else:
            counts['accessible']+=1
            counts['fixed_margin' if margin_type==MARGIN_FIXED else 'normal_margin']+=1
            counts['chart_following' if chart_sign==1 else 'chart_contrarian']+=1
            counts[f'margin_{margin_type}_chart_{chart_sign}']+=1
            if time==0: counts['market_time_zero']+=1
            if window==0: counts['configured_window_zero']+=1
            if mean_reversion==0: counts['mean_reversion_zero']+=1
            if equality: counts['forced_expected_price_equality']+=1
            if not original and margin_type==MARGIN_NORMAL:
                counts['normal_no_order_still_two_gauss']+=1
        rows.append([float(accessible),current,fundamental,past,time,window,mean_reversion,
                     *weights,noise_scale,chart_sign,margin_type,margin,g1,g2])
        if original:
            counts['buy' if original[0][2] else 'sell'] += 1
        oracle.append(original)
        metadata.append((ai,market_id))
        counts['orders' if original else 'no_order']+=1

x=np.asarray(rows,dtype=np.float64)
serial=fcn_probe.evaluate(x,1,'serial')
mismatches=[]
for i,y in enumerate(serial):
    orders=[]
    if y[0]:
        ai,market_id=metadata[i]
        orders=[Order(agent_id=ai,market_id=market_id,is_buy=y[0]==1.0,
                      kind=LIMIT_ORDER,volume=int(y[2]),price=float(y[1]),ttl=int(y[3]))]
    candidate=tuple(map(order_key, orders))
    no_order_fields_match = bool(y[0]) or all(float(v).hex() == '0x0.0p+0' for v in y[:4])
    if candidate != oracle[i] or not no_order_fields_match or y[0] not in (-1.0, 0.0, 1.0):
        mismatches.append({'row': i, 'oracle': oracle[i], 'native': candidate,
                           'native_row_hex': [float(v).hex() for v in y]})

hash_value=hashlib.sha256(serial.tobytes()).hexdigest()
parallel=[]
for schedule in ['static','dynamic']:
    for workers in [1,2,4]:
        result=fcn_probe.evaluate(x,workers,schedule)
        parallel.append({'schedule':schedule,'workers':workers,
                         'bytewise_equal_to_serial':serial.tobytes()==result.tobytes(),
                         'output_sha256':hashlib.sha256(result.tobytes()).hexdigest()})
required_coverage = (
    'margin_0_chart_1', 'margin_0_chart_-1', 'margin_1_chart_1', 'margin_1_chart_-1',
    'inaccessible_no_rng_consumption', 'normal_no_order_still_two_gauss',
    'market_time_zero', 'configured_window_zero', 'mean_reversion_zero',
    'agents_initial_gauss_cache_nonempty', 'forced_expected_price_equality', 'buy', 'sell',
)
missing_coverage = [name for name in required_coverage if not counts[name]]
records={
 'scope':'Feasibility differential probe of FCN pure numerical kernel against actual PAMS function, not full simulation correctness or speedup',
 'upstream_repository':'https://github.com/masanorihirano/pams',
 'upstream_commit':PAMS_COMMIT,
 'upstream_function':'pams/agents/fcn_agent.py::FCNAgent.submit_orders_by_market',
 'upstream_file_sha256':FCN_SHA256,
 'license':'EPL-1.0 for adapted numerical expression; LICENSE retained',
 'taskflow_version':'v3.11.0',
 'taskflow_sha':'816b4ad53b44196c88f409eb7b4a25a0e3bfdf42',
 'pybind11_version':'v2.13.6',
 'pybind11_sha':'a2e59f0e7065404b44dfe92a28aca47ba1378dc4',
 'python':sys.version,'platform':platform.platform(),'numpy':np.__version__,
 'scipy':importlib.metadata.version('scipy'), 'tqdm':importlib.metadata.version('tqdm'),
 'generated_cases':len(rows),'generation_seed':20261125,
 'agents':100,'calls_per_agent':100,'per_agent_rng_seed':'700001+agent_id',
 'coverage':dict(counts),
 'missing_required_coverage':missing_coverage,
 'python_oracle_price_hex_side_volume_ttl_identity_mismatches':len(mismatches),
 'mismatch_examples':mismatches[:10],
 'python_random_state_or_gauss_count_mismatches':len(rng_mismatches),
 'rng_mismatch_examples':rng_mismatches[:10],
 'native_serial_output_sha256':hash_value,'thread_checks':parallel,
 'limits':['Valid finite domain only; invalid-input exception parity not tested',
           'Uses actual Market/FCNAgent/Order classes but hand-initialized market histories',
           'Does not test runner early-stop, event hooks, HFT interleaving, fill/settlement semantics',
           'Results apply only to recorded toolchain and environment; cross-platform bitwise equality not established',
           'No timing/performance or cache measurements were made']}
print(json.dumps(records,indent=2))
ok=(len(rows) == 10000 and not missing_coverage and not mismatches and not rng_mismatches
    and all(r['bytewise_equal_to_serial'] for r in parallel))
raise SystemExit(0 if ok else 1)
