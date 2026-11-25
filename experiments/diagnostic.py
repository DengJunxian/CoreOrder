"""Low-overhead and cProfile paths are separate DEVELOPMENT diagnostics.

No full trace or checkpoint in low-overhead mode. Not the frozen E4 experiment driver.
SPDX-License-Identifier: EPL-1.0
"""
import argparse
from collections import Counter
import copy
import cProfile
import hashlib
from pathlib import Path
import random
import time

from validation.codec import dumps,encode,snapshot,digest
from validation.io import read,write


def run(config,seed,pams_root,profile_path=None):
    from validation.upstream import load
    load(pams_root)
    from pams.runners import SequentialRunner
    from pams.logs import Logger
    class CompactLogger(Logger):
        def __init__(self):
            super().__init__()
            self.counts=Counter()
            self.hasher=hashlib.sha256()
            self.event_seq=0
        def capture(self,log):
            session=self.simulator.current_session
            row={"event_seq":self.event_seq,"session":getattr(session,"session_id",None),
                 "step":min((m.get_time() for m in self.simulator.markets),default=-1),
                 "type":type(log).__name__,"fields":encode(vars(log))}
            # Stream index has an explicit newline delimiter; differs from array hash.
            self.hasher.update((dumps(row)+"\n").encode())
            self.event_seq+=1
            self.counts[type(log).__name__]+=1
        def write(self,log):
            self.capture(log)
            super().write(log)
        def write_and_direct_process(self,log):
            self.capture(log)
            super().write_and_direct_process(log)
        def bulk_write(self,logs):
            for log in logs:self.capture(log)
            super().bulk_write(logs)
        def bulk_write_and_direct_process(self,logs):
            for log in logs:self.capture(log)
            super().bulk_write_and_direct_process(logs)
    logger=CompactLogger()
    start=time.perf_counter()
    runner=SequentialRunner(settings=copy.deepcopy(config),prng=random.Random(seed),logger=logger)
    runner._setup()
    setup=time.perf_counter()-start
    profiler=cProfile.Profile() if profile_path else None
    start=time.perf_counter()
    if profiler:profiler.enable()
    runner._run()
    logger._process()
    if profiler:profiler.disable()
    simulation=time.perf_counter()-start
    if profiler:profiler.dump_stats(str(profile_path))
    final=snapshot(runner.simulator,runner._prng)  # deliberately outside timing
    return {"measurement_mode":"profile" if profiler else "low-overhead-diagnostic",
            "setup_s":setup,"simulation_s":simulation,"event_counts":dict(logger.counts),
            "event_stream_hash":logger.hasher.hexdigest(),"final_hash":digest(final),"rng_hash":digest(final["rng"]),
            "scope":"DEVELOPMENT ONLY; streaming event encoding remains in timed business path",
            "counters_missing":{"agent_calls":"not instrumented","decision_rows":"not instrumented",
                                "native_rows":"not applicable","gauss_api_calls":"not instrumented"}}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--config",required=True)
    p.add_argument("--pams-root",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--profile",action="store_true")
    p.add_argument("--seed",type=int,default=42)
    a=p.parse_args()
    root=Path(a.output)
    root.mkdir(parents=True,exist_ok=False)
    result=run(read(a.config),a.seed,a.pams_root,root/"profile.prof" if a.profile else None)
    from experiments.capture import environment,git
    result.update(git_sha=git("rev-parse","HEAD"),dirty=bool(git("status","--porcelain")),
                  seed=a.seed,input_hash=digest(read(a.config)))
    write(root/"diagnostic.json",result)
    write(root/"environment.json",environment())
    print(result["measurement_mode"],result["event_counts"],result["final_hash"])


if __name__=="__main__":
    main()
