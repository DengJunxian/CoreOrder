"""Bridge production runs to E's existing semantic observation points."""

import subprocess
import sys

from validation.codec import digest
from validation.collector import ObservedSimulator, TraceLogger
from validation.compare import compare, save_reproducer
from validation.io import read, write
from validation.stream import compare_streams, save_difference

from .config import ROOT
from .snapshot import PamsObservations


def compare_upstream(output, seed, reference=None, *, streamed=False):
    if reference is None:
        reference = output / "reference-trace.json.gz"
        command = [sys.executable, "-m", "validation", "collect", "--config", str(output / "workload.json"),
                   "--pams-root", str(ROOT / "vendor/pams"), "--seed", str(seed), "--output", str(reference)]
        if streamed:
            command.append("--stream")
        result = subprocess.run(command, cwd=ROOT, check=False)
        write(output / "reference-command.json", {"command": command, "exit_code": result.returncode})
        if result.returncode != 0:
            return {"status": "FAIL", "scope": "upstream reference collection"}
    candidate_path = output / "validation-trace.json.gz"
    if streamed:
        report = compare_streams(reference, candidate_path)
        if report["status"] == "FAIL":
            save_difference(report, reference, candidate_path, output / "first-divergence")
        return report
    original, candidate = read(reference), read(candidate_path)
    report = compare(original, candidate)
    if report["status"] == "FAIL":
        save_reproducer(original, candidate, output / "first-divergence")
    return report


class ValidationObservations(PamsObservations, TraceLogger):
    @staticmethod
    def trace_metadata(settings, seed, manifest):
        return {"contract_version": manifest["contract_version"], "upstream_sha": manifest["upstream_sha"],
                "config": settings, "input_hash": digest(settings), "seed": seed,
                "backend_requested": manifest["backend_requested"], "backend_effective": manifest["backend_requested"],
                "book_restore": manifest["book_restore"]}

    def after_setup(self, runner):
        self.runner_rng = runner._prng
        self.initial = self.state()
        if self.stream:
            self.stream.emit("initial", self.initial)
            self.initial = None

    def __getstate__(self):
        state = super().__getstate__()
        state.pop("initial", None)
        state.pop("stream", None)
        return state

    def state(self):
        result = super().state()
        if self.restore == "incremental":
            # The approved class adds one non-financial instance field.
            for market in result["state"]["markets"]:
                if market.pop("book_restore") != "incremental":
                    raise ValueError("incremental trace has inconsistent market restore mode")
        return result

    def process_market_step_end_log(self, log):
        if self.stream:
            self.market_steps += 1
        else:
            super().process_market_step_end_log(log)

    def write_trace(self, output, settings, seed, manifest, runner):
        final = self.state()
        if self.stream:
            self.stream.emit("final", final)
        else:
            write(output / "validation-trace.json.gz", {
                **self.trace_metadata(settings, seed, manifest), "events": self.events, "steps": self.steps,
                "initial": self.initial["state"], "final": final["state"], "rng": final["state"]["rng"],
            })
