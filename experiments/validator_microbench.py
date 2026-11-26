"""E's own traversal microbenchmark on a real upstream trace.

Not a simulation/native/layout speedup result. SPDX-License-Identifier: EPL-1.0
"""
import argparse
import copy
import statistics
import time

from validation.codec import digest,dumps
from validation.compare import compare
from validation.io import read,write


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--trace",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    left=read(a.trace)
    right=copy.deepcopy(left)
    compare(left,right)
    samples=[]
    for _ in range(7):
        start=time.perf_counter_ns()
        report=compare(left,right)
        samples.append(time.perf_counter_ns()-start)
        assert report["status"]=="PASS"
    from experiments.capture import environment,git
    result={"kind":"validator-traversal-microbenchmark","formal_system_performance":False,
            "git_sha":git("rev-parse","HEAD"),"dirty":bool(git("status","--porcelain")),
            "trace_content_hash":digest(left),"trace_input_hash":left["input_hash"],"seed":left["seed"],
            "events":len(left["events"]),"checkpoints":len(left["steps"]),
            "canonical_json_bytes":len(dumps(left).encode()),"warmups":1,"technical_repeats":7,
            "samples_ns":samples,"median_ns":statistics.median(samples),
            "time_boundary":"Only compare on preloaded independent equal structures; excludes IO/setup",
            "environment":environment(),"limitation":"One real fixture, warm memory, development tree; no E2E inference"}
    write(a.output,result)
    print(result["kind"],"events",result["events"],"median_ns",result["median_ns"])


if __name__=="__main__":
    main()
