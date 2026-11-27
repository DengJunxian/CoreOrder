"""The stream represents all legacy oracle values and rejects a one-word RNG fault."""

import base64
import json
from pathlib import Path

from validation.compare import compare
from validation.invariants import check
from validation.io import read
from validation.reference import collect
from validation.stream import Checkpoints, MT_WORDS, compare_streams, conservation, frames

ROOT = Path(__file__).resolve().parents[2]


def test_real_pams_checkpoint_stream_roundtrip_and_rng_fault(tmp_path):
    config = read(ROOT / "configs/experiments/workloads/c01/C01b-normal.json")
    legacy = collect(config, 11, ROOT / "vendor/pams")
    path = tmp_path / "stream.gz"
    collect(config, 11, ROOT / "vendor/pams", stream_path=path)
    assert conservation(path) == check(legacy)
    assert compare_streams(path, path)["status"] == "PASS"

    words = []
    decoded = {"events": [], "steps": []}

    def expand(value):
        if isinstance(value, list):
            return [expand(item) for item in value]
        if not isinstance(value, dict):
            return value
        if set(value) == {"mt19937"}:
            version, pointer, index, gaussian = value["mt19937"]
            return {"python_random": [version, [*words[pointer], index],
                                      None if gaussian is None else {"float_hex": gaussian}]}
        return {key: expand(item) for key, item in value.items()}

    new = None
    faulted = False
    bad = tmp_path / "fault.gz"
    try:
        for channel, payload in frames(path):
            frame = json.loads(payload)
            if channel == "metadata":
                decoded.update(frame)
                new = Checkpoints(bad, frame)
                continue
            expanded = dict(frame)
            if "mt_words" in frame:
                words.extend(MT_WORDS.unpack(base64.b64decode(value)) for value in expanded.pop("mt_words"))
                expanded["state"] = expand(frame["state"])
            if channel in ("events", "steps"):
                decoded[channel].append(expanded)
            else:
                decoded[channel] = expanded["state"]
            if channel == "initial":
                data = bytearray(base64.b64decode(frame["mt_words"][0]))
                data[0] ^= 1
                frame["mt_words"][0] = base64.b64encode(data).decode("ascii")
                faulted = True
            new.emit(channel, frame)
    finally:
        if new is not None:
            new.file.close()
    decoded["rng"] = decoded["final"]["rng"]
    assert compare(legacy, decoded)["status"] == "PASS"
    assert faulted
    failure = compare_streams(path, bad)
    assert failure["status"] == "FAIL" and failure["scope"] == "initial"
    assert failure["difference"]["path"].startswith("$/mt_words/")
