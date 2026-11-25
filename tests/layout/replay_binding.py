"""Replay A's FCN fixture through D's buffers and B's production serial binding.

Set PYTHONPATH to the D source directory and, for a prebuilt binding, its build
directory. Pass the fixtures/pams directory as the positional argument.
Windows can build the unmodified B sources in a temporary directory by passing
--build-msvc B_CHECKOUT from a Visual Studio x64 Developer Command Prompt.
"""

import argparse
import hashlib
import json
import platform
import runpy
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

import numpy as np

from coreorder.packing import INPUT_DTYPE, METADATA_DTYPE, OUTPUT_DTYPE, LayoutBuffer, validate_output


def build_msvc(root, destination):
    import pybind11

    source_files = ["native/fcn/evaluate.cpp", "native/bindings/fcn_binding.cpp",
                    "native/bindings/module.cpp"]
    for rel in [*source_files, "native/bindings/fcn_binding.hpp", "include/coreorder/contracts.hpp"]:
        print(rel, hashlib.sha256((root / rel).read_bytes()).hexdigest())
    args = ["cl", "/LD", "/std:c++17", "/EHsc", "/O2", "/fp:strict", "/MD",
            f"/I{root / 'include'}", f"/I{sysconfig.get_path('include')}", f"/I{pybind11.get_include()}",
            *(str(root / name) for name in source_files), "/link",
            f"/LIBPATH:{Path(sys.base_prefix) / 'libs'}", "/OUT:_coreorder_fcn.pyd"]
    print(subprocess.list2cmdline(args), flush=True)
    subprocess.run(args, check=True, cwd=destination)
    sys.path.insert(0, str(destination))


def replay(fixtures):
    import _coreorder_fcn

    print("production binding", _coreorder_fcn.__file__)
    contracts = runpy.run_path(str(fixtures.resolve().parents[1] / "src/coreorder/contracts.py"))
    for key, dtype in [("INPUT_DTYPE", INPUT_DTYPE), ("OUTPUT_DTYPE", OUTPUT_DTYPE)]:
        if contracts[key] != dtype or contracts[key].alignment != dtype.alignment:
            raise AssertionError(f"A and D disagree on {key}")
    payload = (fixtures / "fcn/rows.jsonl").read_bytes()
    manifest = json.loads((fixtures / "manifest.json").read_bytes())
    digest = hashlib.sha256(payload).hexdigest()
    if digest != manifest["files"]["fcn/rows.jsonl"]:
        raise ValueError("public fixture hash mismatch")
    entries = [json.loads(line) for line in payload.splitlines()]
    if not entries:
        raise ValueError("empty public fixture")
    print("input SHA256", digest, "rows", len(entries), "PAMS", manifest["pams_sha"],
          "fixture environment", manifest["environment"], "seed", manifest["seed"])
    evaluator = _coreorder_fcn.Evaluator(parallel=False)
    rows = []
    metadata = []
    expected = np.empty(len(entries), dtype=OUTPUT_DTYPE)
    for i, entry in enumerate(entries):
        data = entry["input"]
        rows.append(tuple(float.fromhex(data[k]) if INPUT_DTYPE[k].kind == "f" else data[k]
                          for k in INPUT_DTYPE.names))
        metadata.append(tuple(entry[k] for k in METADATA_DTYPE.names))
        output = entry["output"]
        expected[i] = (float.fromhex(output["price"]), output["side"], output["error"])

    def populate(writer):
        for i, row in enumerate(rows):
            writer.set_row(i, row, metadata[i])

    results = {}
    for layout in ("aos", "soa"):
        storage = LayoutBuffer(layout)
        with storage.packed(len(rows), populate) as view:
            if view.metadata.tolist() != metadata:
                raise AssertionError(f"{layout}: metadata differs")
            result = getattr(evaluator, layout)(view.inputs)
            validate_output(result, len(rows))
            results[layout] = result
            print(layout, "output SHA256", hashlib.sha256(result.tobytes()).hexdigest(),
                  "stats", json.dumps(view.stats))
    if results["aos"].tobytes() != results["soa"].tobytes():
        raise AssertionError("layouts differ in output bytes")
    print("AoS vs SoA: all output bytes identical")
    mismatches = [i for i in range(len(entries)) if expected[i].tobytes() != results["aos"][i].tobytes()]
    print("B vs recorded oracle mismatching row indices", mismatches)
    for i in mismatches:
        print(i, "actual", results["aos"][i].tobytes().hex(), "expected", expected[i].tobytes().hex())
    if mismatches:
        raise AssertionError("recorded oracle differs (inspect fixture and local environments)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", type=Path)
    parser.add_argument("--build-msvc", type=Path)
    args = parser.parse_args()
    print("python", sys.version, "numpy", np.__version__, "host", platform.platform())
    if args.build_msvc:
        # Windows keeps an imported .pyd mapped until process exit. Build in a
        # fresh directory below the user's temporary folder, reported in stdout.
        build_dir = Path(tempfile.mkdtemp(prefix="coreorder-d-replay-"))
        build_msvc(args.build_msvc.resolve(), build_dir)
    replay(args.fixtures)
