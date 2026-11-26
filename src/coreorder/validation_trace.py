"""Bridge production runs to E's existing semantic observation points."""

from validation.codec import digest, snapshot
from validation.collector import ObservedSimulator, TraceLogger
from validation.io import write

from .snapshot import PamsObservations


class ValidationObservations(PamsObservations, TraceLogger):
    def after_setup(self, runner):
        self.runner_rng = runner._prng
        self.initial = snapshot(runner.simulator, self.runner_rng)

    def __getstate__(self):
        # Checkpoints are taken on the controlling process.
        state = super().__getstate__()
        state.pop("initial", None)
        return state

    def write_trace(self, output, settings, seed, manifest, runner):
        final = snapshot(runner.simulator, self.runner_rng)
        if manifest["book_restore"] == "incremental":
            # The approved class adds exactly one non-financial instance field.
            for state in (self.initial, final, *(step["state"] for step in self.steps)):
                for market in state["markets"]:
                    if market.pop("book_restore") != "incremental":
                        raise ValueError("incremental trace has inconsistent market restore mode")
        write(output / "validation-trace.json.gz", {
            "contract_version": manifest["contract_version"], "upstream_sha": manifest["upstream_sha"],
            "config": settings, "input_hash": digest(settings), "seed": seed,
            "backend_requested": manifest["backend_requested"], "backend_effective": manifest["backend_effective"],
            "book_restore": manifest["book_restore"], "events": self.events, "steps": self.steps,
            "initial": self.initial, "final": final, "rng": final["rng"],
        })
