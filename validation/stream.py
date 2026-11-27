"""Lossless checkpoint stream for full-run E validation on bounded memory."""

import base64
import gzip
import json
import struct
from itertools import zip_longest
from pathlib import Path

from .codec import dumps, snapshot
from .compare import first_diff
from .invariants import check

FORMAT = "coreorder-e-checkpoint-stream-v1"
IDENTITY = ("contract_version", "upstream_sha", "input_hash", "seed")
MT_WORDS = struct.Struct("<624I")
CHANNELS = ("events", "steps", "final", "initial")


class Checkpoints:
    def __init__(self, path, metadata):
        self.file = gzip.GzipFile(filename=str(path), mode="xb", mtime=0, compresslevel=1)
        self.previous = {}
        self.words = {}
        self.emit("metadata", {**metadata, "format": FORMAT})

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.file.close()

    def emit(self, channel, value):
        self.file.write(channel.encode("ascii") + b"\t" + dumps(value).encode("ascii") + b"\n")

    def state(self, simulator, runner_rng):
        frame_cache = {}
        definitions = []

        def rng(random):
            if random in frame_cache:
                return frame_cache[random]
            version, state, gaussian = random.getstate()
            if version != 3 or len(state) != 625:
                raise ValueError("unsupported Python RNG representation")
            words = state[:-1]
            old = self.previous.get(random)
            if old is not None and old[0] == words:
                key = old[1]
            else:
                packed = MT_WORDS.pack(*words)
                if packed not in self.words:
                    self.words[packed] = len(self.words)
                    definitions.append(base64.b64encode(packed).decode("ascii"))
                key = self.words[packed]
                self.previous[random] = (words, key)
            result = {"mt19937": [version, key, state[-1],
                                  None if gaussian is None else float(gaussian).hex()]}
            frame_cache[random] = result
            return result

        return snapshot(simulator, runner_rng, python_rng=rng), definitions


def frames(path):
    with gzip.open(path, "rb") as file:
        for line in file:
            if not line.endswith(b"\n"):
                raise ValueError("partial checkpoint frame")
            channel, delimiter, data = line[:-1].partition(b"\t")
            if not delimiter:
                raise ValueError("missing checkpoint frame delimiter")
            yield channel.decode("ascii"), data


def metadata(path):
    channel, payload = next(frames(path), ("", b""))
    if channel != "metadata":
        raise ValueError("checkpoint stream has no metadata")
    result = json.loads(payload)
    if result["format"] != FORMAT:
        raise ValueError("unsupported checkpoint stream format")
    return result


def inventory(path):
    counts = dict.fromkeys(CHANNELS, 0)
    source = frames(path)
    if next(source, ("", b""))[0] != "metadata":
        raise ValueError("checkpoint stream has no metadata")
    for channel, data in source:
        if channel not in counts or counts["final"] or (counts["initial"] == 0 and channel != "initial"):
            raise ValueError("invalid checkpoint stream ordering")
        counts[channel] += 1
    if counts["initial"] != 1 or counts["final"] != 1:
        raise ValueError("checkpoint stream missing initial/final state")
    return counts


def values(path, channel):
    for name, raw in frames(path):
        if name == channel:
            yield json.loads(raw)


def conservation(path):
    # The independent invariants inspect accounts and events; RNG words are compared separately.
    initial = next(values(path, "initial"))["state"]
    final = next(values(path, "final"))["state"]
    return check({"initial": initial, "steps": values(path, "steps"), "final": final,
                  "events": values(path, "events")})


def compare_streams(reference, candidate):
    left, right = metadata(reference), metadata(candidate)
    for key in IDENTITY:
        if key not in left or key not in right or left[key] != right[key]:
            return {"status": "FAIL", "scope": "identity", "difference": {
                "path": key, "reference": left.get(key), "candidate": right.get(key)}}
    counts = dict.fromkeys(CHANNELS, 0)
    for (channel, raw), (other, observed) in zip_longest(frames(reference), frames(candidate),
                                                      fillvalue=("", b"null")):
        if channel == other == "metadata":
            continue
        if channel != other or raw != observed:
            a, b = json.loads(raw), json.loads(observed)
            return {"status": "FAIL", "scope": channel or other, "index": counts.get(channel),
                    "location": {k: a[k] for k in ("session", "step", "next_market_times") if isinstance(a, dict) and k in a},
                    "difference": first_diff(a, b) if channel == other else {"reference": channel, "candidate": other}}
        counts[channel] += 1
    if counts["final"] != 1 or counts["initial"] != 1:
        raise ValueError("missing complete state frames")
    return {"status": "PASS", "scopes": ["events", "steps", "final", "rng", "initial"], "counts": counts}


def save_difference(report, reference, candidate, directory):
    from .io import write
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    write(directory / "config.json", metadata(reference)["config"])
    write(directory / "first_divergence.json", {**report, "reference_origin": str(reference),
                                                "candidate_origin": str(candidate)})
