"""Bounded independent C01 development matrix. Native cells remain pending.

SPDX-License-Identifier: EPL-1.0
"""
import argparse
from collections import Counter
from pathlib import Path
import time

from .cases import cases
from .codec import digest
from .compare import compare, save_reproducer
from .invariants import check
from .io import write
from .reference import collect
from .records import TIMES,validate_record
from . import CONTRACT,PAMS_SHA

SEEDS=(101,202,303,404,505)
NATIVE_SETTINGS=(
    {"backend":"native-serial","book_restore":"upstream","layout":"aos"},
    {"backend":"native-serial","book_restore":"upstream","layout":"soa"},
    {"backend":"native-parallel","book_restore":"incremental","layout":"aos","workers":1},
    {"backend":"native-parallel","book_restore":"incremental","layout":"aos","workers":2},
    {"backend":"native-parallel","book_restore":"incremental","layout":"soa","workers":4},
)


def run_records(root,name,seed,config,trace,comparison,source,env_hash):
    run_id=f"{root.name}-{name}-{seed}-{trace['backend_effective']}"
    manifest=dict(run_id=run_id,experiment_id="C01-development",workload_id=name,
        protocol_hash=digest({"cases":12,"seeds":SEEDS,"settings":"seq/thread+5 pending native"}),
        git_sha=source["git_sha"],dirty=source["dirty"],upstream_sha=PAMS_SHA,contract_version=CONTRACT,
        backend_requested=trace["backend_requested"],backend_effective=trace["backend_effective"],
        book_restore="upstream",numeric_mode="libm",layout="not_applicable",
        workers=1 if trace["backend_effective"]=="py-seq" else 2,seed=seed,repeat=0,warmup=False,
        host_id=source["host_id"],input_hash=trace["input_hash"],environment_hash=env_hash,
        block_id=None,pairing_group_id=None,order_seed=None,order_position=None,
        pairing_not_applicable_reason="Independent correctness validation, not paired performance timing",
        grain=None,schedule="not_applicable",N=len(trace["final"]["agents"]),
        M=config["simulation"]["sessions"][0]["maxNormalOrders"],K=len(trace["final"]["markets"]),
        steps=sum(s["iterationSteps"] for s in config["simulation"]["sessions"]),
        time_boundary="Full trace validation; no runtime measurement",measurement_tool="PAMS logger + E observer")
    metrics={key:None for key in TIMES}
    metrics.update(missing_reasons={key:"Not collected in full-trace correctness mode" for key in TIMES},
                   metric_sources={},measurement_mode="validation")
    status=dict(run_id=run_id,status="PASS",validation_status=comparison["status"],
                reference_run_id=f"{root.name}-{name}-{seed}-py-seq",
                trace_hash=trace["hashes"]["events"],final_state_hash=trace["hashes"]["final"],
                rng_hash=trace["hashes"]["rng"],comparison_scope="events/steps/final/rng",censoring=None)
    validate_record(manifest,metrics,status)
    for filename,value in (("manifest.json",manifest),("metrics.json",metrics),("status.json",status)):
        write(root/"records"/run_id/filename,value)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--pams-root",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--budget-seconds",type=float,default=240)
    a=p.parse_args()
    root=Path(a.output)
    root.mkdir(parents=True,exist_ok=False)
    from experiments.capture import environment,git
    env=environment()
    write(root/"environment.json",env)
    import platform
    source={"git_sha":git("rev-parse","HEAD"),"dirty":bool(git("status","--porcelain")),"host_id":platform.node()}
    start=time.perf_counter()
    rows=[]
    for name,config in cases(a.pams_root).items():
        write(root/"configs"/(name+".json"),config)
        for seed in SEEDS:
            if time.perf_counter()-start>a.budget_seconds:
                raise TimeoutError("development matrix budget exhausted; partial raw preserved")
            oracle=collect(config,seed,a.pams_root)
            write(root/"traces"/f"{name}-{seed}-py-seq.json.gz",oracle)
            row={"case":name,"seed":seed,"input_hash":digest(config),"oracle_hashes":oracle["hashes"],
                 "event_counts":dict(Counter(e["type"] for e in oracle["events"])),
                 "invariants":check(oracle),"native_status":"INTEGRATION_PENDING",
                 "native_reason":"A/B/C/D production candidates and unified CLI not delivered"}
            candidate=collect(config,seed,a.pams_root,"py-thread",2)
            write(root/"traces"/f"{name}-{seed}-py-thread.json.gz",candidate)
            comparison=compare(oracle,candidate)
            row.update(thread_comparison=comparison,thread_hashes=candidate["hashes"],thread_invariants=check(candidate))
            validation_result=comparison if row["invariants"]["status"]==row["thread_invariants"]["status"]=="PASS" else {"status":"FAIL"}
            run_records(root,name,seed,config,oracle,validation_result,source,digest(env))
            run_records(root,name,seed,config,candidate,validation_result,source,digest(env))
            write(root/"rows"/f"{name}-{seed}.json",row)
            rows.append(row)
            if comparison["status"]!="PASS":
                save_reproducer(oracle,candidate,root/"failures"/f"{name}-{seed}")
            print(name,seed,comparison["status"],row["invariants"]["status"],flush=True)
    pending=[{"case":name,"seed":seed,**setting,"status":"NOT_RUN","integration_status":"INTEGRATION_PENDING"}
             for name in cases(a.pams_root) for seed in SEEDS for setting in NATIVE_SETTINGS]
    summary={"module_status":"MODULE_PASS" if all(r["thread_comparison"]["status"]==r["invariants"]["status"]==r["thread_invariants"]["status"]=="PASS" for r in rows) else "FAIL",
             "system_gate":"INTEGRATION_PENDING","git_sha":git("rev-parse","HEAD"),
             "dirty":bool(git("status","--porcelain")),"seeds":list(SEEDS),"rows":len(rows),
             "actual_upstream_runs":len(rows)*2,"pending_native_cells":pending,
             "process_note":"Separate bounded subprocess attempt, see E2/process-command",
             "measurement_scope":"correctness trace only; no formal timing"}
    write(root/"summary.json",summary)
    print(summary["module_status"],"runs",summary["actual_upstream_runs"],"native pending",len(pending))
    return 0 if summary["module_status"]=="MODULE_PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
