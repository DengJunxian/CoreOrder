"""D3 module diagnostic: pack one fixed terminal PAMS snapshot in both layouts."""

import argparse
import hashlib
import inspect
import json
import platform
import random
import statistics
from importlib.metadata import version
from pathlib import Path
from time import perf_counter_ns

from pams.agents.fcn_agent import FCNAgent, MARGIN_FIXED
from pams.market import Market
from pams.runners.sequential import SequentialRunner

from coreorder.packing import Draw, INPUT_DTYPE, LayoutBuffer, pack_batch


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(view):
    # Canonical field order makes the hash independent of physical strides.
    digest = hashlib.sha256()
    for field in INPUT_DTYPE.names:
        digest.update(view.inputs[field].tobytes())
    digest.update(view.metadata.tobytes())
    return digest.hexdigest()


def run(fixture, repeats):
    manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))
    config = fixture / "fcn" / "fixed.json"
    if file_hash(config) != manifest["files"]["fcn/fixed.json"]:
        raise ValueError("public fixed.json differs from the fixture manifest")
    pams_sha = "6cd53810103780770c5b5d6ee0069ccab9f4b358"
    if manifest["pams_sha"] != pams_sha or manifest["seed"] != 42:
        raise ValueError("unexpected PAMS fixture revision or seed")
    runner = SequentialRunner(settings=json.loads(config.read_text()), prng=random.Random(42))
    runner.main()
    agents = runner.simulator.agents
    markets = runner.simulator.markets
    if len(agents) != 24 or not all(type(agent) is FCNAgent and agent.margin_type == MARGIN_FIXED
                                    for agent in agents):
        raise ValueError("this diagnostic requires the public 24-agent fixed-margin workload")

    # Copy each terminal PRNG state, including any pending Gaussian. The runner
    # and the agents are never advanced after the terminal snapshot.
    states = [agent.prng.getstate() for agent in agents]
    samples = []
    for agent, state in zip(agents, states):
        clone = random.Random(0)
        clone.setstate(state)
        for market in markets:
            if agent.is_market_accessible(market.market_id):
                samples.append(Draw(agent.agent_id, market.market_id, clone.gauss(0.0, 1.0)))

    buffers = {layout: LayoutBuffer(layout) for layout in ("aos", "soa")}
    warmup = 4
    for buffer in buffers.values():
        for _ in range(warmup):
            with pack_batch(buffer, agents, markets, samples):
                pass

    observations = []
    stats = {}
    hashes = set()
    for block in range(repeats):
        order = ("aos", "soa") if block % 2 == 0 else ("soa", "aos")
        for position, layout in enumerate(order):
            buffer = buffers[layout]
            start = perf_counter_ns()
            with pack_batch(buffer, agents, markets, samples):
                pass
            elapsed = perf_counter_ns() - start
            observations.append(dict(block=block, position=position, layout=layout, elapsed_ns=elapsed))
            with buffer.read() as view:
                hashes.add(fingerprint(view))
                stats[layout] = view.stats
    if len(hashes) != 1:
        raise RuntimeError("packed rows or metadata diverged")
    if [agent.prng.getstate() for agent in agents] != states:
        raise RuntimeError("packing changed an agent RNG")
    repo = Path(__file__).resolve().parents[2]
    return {
        "scope": "D3 pack_batch entry through context exit, including view/stat creation and release",
        "excluded": ["runner.main", "terminal state sampling", "hashing", "native compute", "order rebuild"],
        "kind": "module_microbenchmark", "contract_version": "coreorder-r4-v1",
        "python": platform.python_version(), "implementation": platform.python_implementation(),
        "platform": platform.platform(), "architecture": platform.machine(),
        "dependencies": {name: version(name) for name in ("numpy", "scipy", "tqdm")},
        "fixture_pams_commit": pams_sha, "seed": 42,
        "sha256": {
            "fixed.json": file_hash(config), "manifest.json": file_hash(fixture / "manifest.json"),
            "pack_micro.py": file_hash(__file__), "packing.py": file_hash(inspect.getfile(pack_batch)),
            "pams/agents/fcn_agent.py": file_hash(inspect.getfile(FCNAgent)),
            "pams/market.py": file_hash(inspect.getfile(Market)),
            "pams/runners/sequential.py": file_hash(inspect.getfile(SequentialRunner)),
            "hardware.json": file_hash(repo / "docs/roles/D/evidence/hardware.json"),
        },
        "agent_order": "simulator.agents order in the terminal snapshot",
        "market_times": [market.get_time() for market in markets], "rows": len(samples),
        "draws": "one next gauss per accessible row from each terminal agent's isolated PRNG clone",
        "warmups_per_layout": warmup, "paired_blocks": repeats, "buffer_stats": stats,
        "row_and_metadata_sha256": hashes.pop(), "agent_rng_unchanged": True,
        "median_ns": {layout: statistics.median(row["elapsed_ns"] for row in observations
                                               if row["layout"] == layout) for layout in buffers},
        "raw": observations,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True, help="A's fixtures/pams directory")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=24)
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")
    result = run(args.fixture, args.repeats)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"rows={result['rows']}, blocks={args.repeats}, median_ns={result['median_ns']}")
